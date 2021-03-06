import logging
import logging.config
import os
import pydicom
import shutil
import common.common_tools as ctools
import common.parallelization as pl
import conversion as convtool
from anatomy_query import (
    # FUNCTIONS
    get_anatomy_info,
    quey_anatomy_from_tables,
)
from gcloud.BigQueryStuff import (
    # FUNCTIONS
    query_string_with_result,
)
from gcloud.StorageBucketStuff import (
    # FUNCTIONS
    download_blob,
    list_blobs,
)
from multiprocessing import (
    # SUBMODULES
    freeze_support,
)
from pydicom.charset import (
    # VARIABLES
    python_encoding,
)
from rightdicom.dcmfix.fix_all import (
    # FUNCTIONS
    fix_dicom,
)
from rightdicom.dcmfix.study_dependent_patches import (
    # FUNCTIONS
    add_anatomy,
)
from rightdicom.dcmvfy.verify import (
    # FUNCTIONS
    verify_dicom,
)

LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': True,
    'formatters': {
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        },
    },
    'handlers': {
        'default': {
            'level': 'DEBUG',
            'formatter': 'standard',
            'class': 'logging.StreamHandler',
            'stream': 'ext://sys.stdout',  # Default is stderr
        },
        'file': {
            'level': 'DEBUG',
            'formatter': 'standard',
            'class': 'logging.FileHandler',
            'filename': './Logs/sampling_log.log',  # Default is stderr
            "mode": "w",
        },
    },
    'loggers': {
        'xxx': {  # root logger
            'handlers': ['default'],
            'level': 'DEBUG',
            'propagate': False
        }
    },
    'root': {  # root logger
            'handlers': ['default', 'file'],
            'level': 'INFO',
            'propagate': False
        }
}
logging.config.dictConfig(LOGGING_CONFIG)
log = logging.getLogger(__name__)
log.debug("Logging is configured.")
anatomic_attribs = ["ImageLaterality" ,
"BodyPartExamined",
"FrameAnatomySequence",
"AnatomicRegionSequence",]

def download_parallel(project_id: str, bucket_name: str, st_uid: str,
                      se_uid: str, destination_dir: str,
                      process_number: int=pl.MAX_NUMBER_OF_THREADS):
    logger = logging.getLogger(__name__)
    prefix = 'dicom/{}/'.format(st_uid)
    if se_uid != '':
        prefix = '{}{}/'.format(prefix, se_uid)
    bl_names = []
    bl_lists = list_blobs(project_id, bucket_name, prefix)
    for bl in bl_lists:
        bl_names.append(bl.name)
    logger.info('Number of blobs to be downloaded {}'.format(len(bl_names)))
    if len(bl_names) == 0:
        return
    if os.path.exists(destination_dir):
        shutil.rmtree(destination_dir)
    os.makedirs(destination_dir)
    ps = pl.ProcessPool(min(len(bl_names), process_number), 'down')
    for i, bl_name in enumerate(bl_names, 1):
        file_name = '{:05d}.dcm'.format(i)
        ps.queue.put(
            (
                download_blob,
                (project_id, bucket_name, bl_name, os.path.join(
                    destination_dir, file_name)
                )
            ))
    ps.queue.join()
    ps.kill_them_all()


def VER(file: str, out_folder: str, log: list, write_meta=False,
        char_set: str = 'ascii'):
    file_name = os.path.basename(file)
    if file_name.endswith('.dcm'):
        file_name = file_name[: -4]
    meta_file = os.path.join(out_folder, file_name + '.xml')
    if write_meta:
        toxml_exe_file = "/Users/afshin/Documents/softwares/"\
            "dcmtk/3.6.5/bin/bin/dcm2xml"
        if not os.path.exists(toxml_exe_file):
            toxml_exe_file = shutil.which('dcm2xml')
            if toxml_exe_file is None:
                print('ERROR: Please install dcm2xml in system path')
                assert(False)
        ctools.RunExe(
            [toxml_exe_file, file, meta_file], '', '',
            env_vars = {
                "DYLD_LIBRARY_PATH":
                "/Users/afshin/Documents/softwares/dcmtk/3.6.5/bin/lib/"})
    else:
        meta_file = ''
    # print('{: = ^120}'.format("DAVID'S"))
    dcm_verify = "/Users/afshin/Documents/softwares/"\
        "dicom3tools/most_recent_exe/dciodvfy"
    if not os.path.exists(dcm_verify):
        dcm_verify = shutil.which('dciodvfy')
        if dcm_verify is None:
            print("Error: install dciodvfy into system path")
            assert(False)
    vfy_file = os.path.join(out_folder, file_name + "_vfy.txt")
    ctools.RunExe(
        [dcm_verify, '-filename', file], vfy_file, '',
        errlog = log, char_encoding=char_set)
    # print('{: = ^120}'.format("MY CODE"))
    my_code_output = verify_dicom(file, False, '')
    ctools.WriteStringToFile(vfy_file, '{:=^120}\n'.format("MY CODE"), True)
    ctools.WriteStringToFile(vfy_file, my_code_output, True)
    return(vfy_file, meta_file)


def FixFile(dicom_file: str, dicom_fixed_file: str,
            log_fix: list, log_david_pre: list, log_david_post: list):
    ds = pydicom.read_file(dicom_file)
    st_uid = ds.StudyInstanceUID
    st_anatomy_info = None
    cl_anatomy_info = None
    for cln, cln_an in anatomy_info.items():
        # if len(cln_an[0][0]) > 1:
        #     print(cln_an[0])
        cl_anatomy_info = cln_an[0]
        if st_uid in cln_an[1]:
            st_anatomy_info = cln_an[1][st_uid]
            break
    if st_anatomy_info is not None:
        bpe, ars = get_anatomy_info(st_anatomy_info)
    if bpe is None and ars[0] is None:
        bpe, ars = get_anatomy_info(cl_anatomy_info)
    add_anatomy(ds, bpe, ars, log_fix)
    # log_mine = []
    # VER(dicom_file, log_david_pre)
    fix_dicom(ds, log_fix)
    # fix_report = print(log_fix)
    pydicom.write_file(dicom_fixed_file, ds)
    # VER(dicom_fixed_file, log_david_post)
    return ds


def GetSeries(keyword: str, value: str):
    if isinstance(value, str):
        value = '"{}"'.format(value)
    study_query = """
                WITH DICOMS AS (
                SELECT STUDYINSTANCEUID, SERIESINSTANCEUID, SOPINSTANCEUID
                FROM {}
                WHERE
                    (SOPCLASSUID = "1.2.840.10008.5.1.4.1.1.2" OR
                    SOPCLASSUID = "1.2.840.10008.5.1.4.1.1.4" OR
                    SOPCLASSUID = "1.2.840.10008.5.1.4.1.1.128") AND
                    {} = {}
                    )
                    SELECT DICOMS.STUDYINSTANCEUID,
                        DICOMS.SERIESINSTANCEUID,
                        DICOMS.SOPINSTANCEUID,
                        COLLECTION_TABLE.GCS_Bucket,
                    FROM DICOMS JOIN
                        {} AS
                        COLLECTION_TABLE ON
                        COLLECTION_TABLE.SOPINSTANCEUID = DICOMS.SOPINSTANCEUID
    """.format(
        '`idc-dev-etl.idc_tcia_mvp_wave0.idc_tcia_dicom_metadata`',
        keyword, value,
        '`idc-dev-etl.idc_tcia_mvp_wave0.idc_tcia_auxilliary_metadata`')
    
    studies = query_string_with_result(study_query)
    stuid = None
    seuid = None
    sopuid = None
    cln_id = None
    if studies is not None:
        for row in studies:
            stuid = row.STUDYINSTANCEUID
            seuid = row.SERIESINSTANCEUID
            sopuid = row.SOPINSTANCEUID
            cln_id = row.GCS_Bucket
            break
    return (stuid, seuid, sopuid, cln_id)


if __name__ == '__main__':
    freeze_support()
    project_id = 'idc-tcia'
    in_folders = ['../Tmp/in']
    out_folders = '../Tmp/out'
    out_folders = os.path.realpath(out_folders)
    series_uid = '1.3.6.1.4.1.14519.5.2.1.4591.4003.945678196635089694147290015292'
    sop_uid = '1.3.6.1.4.1.14519.5.2.1.3671.4004.233818514332124445394742500894'
    study_uid, series_uid, instance_uid, bucket_name = GetSeries(
        'SeriesInstanceUID', series_uid)
    # bucket_name = 'idc-tcia-tcga-blca'
    # study_uid = '1.3.6.1.4.1.14519.5.2.1.6354.4016.292170230498352399648594035286'
    # series_uid = '1.3.6.1.4.1.14519.5.2.1.6354.4016.316228581410299389630475076825'
    # instance_uid = '1.3.6.1.4.1.14519.5.2.1.6354.4016.161670751003027974162100121182'

    log = []
    log_ver = []
    fix_: bool = True
    download_ : bool = True
    global anatomy_info
    anatomy_info = {}
    anatomy_info = quey_anatomy_from_tables(
        '`idc-dev-etl.idc_tcia_mvp_wave0.idc_tcia_dicom_metadata`',
        '`idc-dev-etl.idc_tcia_mvp_wave0.idc_tcia_auxilliary_metadata`')
    for i in range(0, len(in_folders)):
        in_folder = os.path.realpath(in_folders[i])
        if download_:
            download_parallel(
                project_id, bucket_name, study_uid, series_uid, in_folder, 88)
        out_folder = os.path.join(out_folders, str(i + 1))
        if os.path.exists(out_folder):
            shutil.rmtree(out_folder)
        os.makedirs(out_folder)
        fix_folder = os.path.join(out_folder, 'fixed')
        if not os.path.exists(fix_folder):
            os.makedirs(fix_folder)
        in_files = ctools.Find(
            in_folder, max_depth = 1, cond_function=ctools.is_dicom)
        if fix_:
            for i, ff in enumerate(in_files):
                fx_log = []
                base = os.path.basename(ff)
                if i % 10 == 0:
                    print('{}/{}) {}'.format(i, len(in_files), base))
                ds = FixFile(ff, os.path.join(fix_folder, base), fx_log, [], [])
                if "SpecificCharacterSet" in ds:
                    dicom_char_set = ds.SpecificCharacterSet
                    if dicom_char_set in python_encoding:
                        python_char_set = python_encoding[dicom_char_set]
                    else:
                        python_char_set = 'ascii'
                # try:
                fx_files = ctools.Find(fix_folder, max_depth=1,
                                                cond_function=ctools.is_dicom)
        else:
            fx_files = in_files
            fix_folder = in_folder
        SOPClassList = convtool.ConvertByHighDicomNew(fix_folder, out_folder, log)
        for n, f in enumerate(SOPClassList, 0):
            output_file_pattern = "hd{:03d}.dcm"
            new_name = os.path.join(out_folder, output_file_pattern.format(n))
            os.rename(f.child_dicom_file, new_name)
        files = ctools.Find(out_folder, 1, lambda x: x.endswith('.dcm'))
        (v_file_pre, m_file_pre) = VER(
            fx_files[0], out_folder, log_ver, char_set=python_char_set)
        print(fx_files[0])
        for f in files:
            (v_file_pre, m_file_pre) = VER(
                f, out_folder, log_ver, char_set=python_char_set)
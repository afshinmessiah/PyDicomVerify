import git
import shutil
from pydicom import *
import pydicom.datadict as Dic
import pydicom.dataelem as Elm
import pydicom.sequence as Seq
from pydicom import uid
import re
from condn_cc import *
from dicom_prechecks import *
import os
from numpy import *
from fix_frequent_errors import *
import curses.ascii
from verify import *
import pydicom.charset
import subprocess
import PrivateDicFromDavid
import os
import xlsxwriter
import time
from datetime import timedelta
import common_tools as ctools
import conversion as conv
from BigQueryStuff import create_all_tables,\
                          query_string,\
                          query_string_with_result
                          
from DicomStoreStuff import list_dicom_stores,\
                            create_dicom_store,\
                            create_dataset,\
                            import_dicom_instance,\
                            export_dicom_instance_bigquery,\
                            exists_dicom_store,\
                            exists_dataset
from DicomWebStuff import dicomweb_retrieve_instance,\
                          _BASE_URL

PROJECT_NAME = 'idc-tcia'
dataset = 'afshin_test00'


class DataInfo:

    def __init__(self, project_id: str,
                 cloud_region: str,
                 bucket_name: str,
                 dicom_store_dataset: str,
                 dicom_store: str,
                 bigquery_dataset: str,
                 bigquery_table: str
                 ):
        self.ProjectID = project_id
        self.CloudRegion = cloud_region
        self.BucketName = bucket_name
        self.DicomStoreDataset = dicom_store_dataset
        self.DicomStore = dicom_store
        self.BigQueryDataset = bigquery_dataset
        self.BigQueryTable = bigquery_table


class MessageError(Exception):

    def __init__(self, original_msg: str):
        self.original_message = original_msg
        self.message = "Message <{}> doesn't have an appropriate format".format(
            self.original_message
        )
        super().__init__(self.message)


class DicomIssue:
    
    def __init__(self, issue_msg: str) -> None:
        self.message = issue_msg
        regexp = '.*(Error|Warning)([-\s]*)(.*)'
        
        m = re.search(regexp, issue_msg)
        if m is None:
            raise MessageError('The issue is not a right type') 
        self.type = m.group(1)
        self.issue_msg = m.group(3)
        issue_pattern = 'T<([^>]*)>\s(.*)'
        m_issue = re.search(issue_pattern, self.issue_msg)
        if m_issue is not None:
            self.issue_short = m_issue.group(1)
            self.issue = m_issue.group(2)
        else:
            self.issue_short = None
        element_pattern = '(Element|attribute|keyword)[=\s]{,5}<([^>]*)>'
        m = re.search(element_pattern, issue_msg)
        if m is not None:
            self.attribute = m.group(2)
        else:
            self.attribute = None
        if self.attribute is not None:
            self.tag = Dic.tag_for_keyword(self.attribute)
        else:
            ptrn = '\(0x([0-9A-Fa-f]{4})[,\s]*0x([0-9A-Fa-f]{4})\)'
            m =  re.search(ptrn, issue_msg)
            if m is not None:
                self.tag = int(m.group(1) + m.group(2), 16)
            else:
                self.tag = None


        module_pattern = '(Module|Macro)[=\s]{,5}<([^>]*)>'
        m = re.search(module_pattern, issue_msg)
        if m is not None:
            self.module_macro = m.group(2)
        else:
            self.module_macro = None

    def GetQuery(self, TableName: str, SOPInstanceUID: uid) -> str:
        out = '''
            (
                {} , -- DCM_TABLE_NAME
                {} , -- DCM_SOP_INSATANCE_UID
                {} , -- ISSUE_MSG
                {} , -- MESSAGE
                {} , -- TYPE
                {} , -- MODULE_MACRO
                {} , -- KEYWORD
                {}   -- TAG
            )
            '''.format(
                self.GetValue(TableName),
                self.GetValue(str(SOPInstanceUID)),
                self.GetValue(self.issue_msg),
                self.GetValue(self.message),
                self.GetValue(self.type),
                self.GetValue(self.module_macro),
                self.GetValue(self.attribute),
                self.GetValue(self.tag)
            )
        return out

    def GetQuery_OLD(self, TableName: str, SOPInstanceUID: uid) -> str:
        out = '''
            CALL `{{0}}`.ADD_TO_ISSUE(
                {},  -- ISSUE_MSG,
                {},  -- MESSAGE,
                {},  -- TYPE,
                {},  -- MODULE_MACRO,
                {},  -- KEYWORD,
                {},  -- TAG,
                {},  -- TABLE_NAME,
                {},  --SOP_INST_UID
                ID   --ID
            );
            '''.format(
                self.GetValue(self.issue_msg),
                self.GetValue(self.message),
                self.GetValue(self.type),
                self.GetValue(self.module_macro),
                self.GetValue(self.attribute),
                self.GetValue(self.tag),
                self.GetValue(TableName),
                self.GetValue(str(SOPInstanceUID))
            )
        return out

    def GetValue(self, v):
        if v is None:
            return "NULL"
        elif type(v) == str:
            return '"{}"'.format(v)
        else:
            return v


class IssueCollection:

    def __init__(self, issues: list, table_name: str, dcmfile:str) -> None:
        self.table_name = table_name
        try: 
            ds = pydicom.read_file(dcmfile, specific_tags = ['SOPInstanceUID'])
            self.SOPInstanceUID = ds['SOPInstanceUID'].value
        except BaseException:
            self.SOPInstanceUID = None
        self.issues: list = []
        for issue in issues:
            try:
                self.issues.append(DicomIssue(issue))
            except BaseException:
                pass

    def GetQueryHeader(self) -> str:
        header = '''
            INSERT INTO `{0}`.ISSUE
                VALUES {1};
        '''
        return header

    def GetQuery(self) -> list:
        q = []
        for i, f in enumerate(self.issues):
            q.append(f.GetQuery(self.table_name, self.SOPInstanceUID))
        return q  


class DicomFix:
    
    def __init__(self, fix_msg: str) -> None:
        self.message = fix_msg
        git_url = 'https://github.com/afshinmessiah/PyDicomVerify/{}'
        repo = git.Repo(search_parent_directories=True)
        commit = repo.head.object.hexsha
        repo = git.Repo(search_parent_directories=True)
        regexp = '([^-]*)\s-\s(.*):-\>:(.*)\<function(.*)from file:(.*)\> \<function(.*)from file:(.*)\>'
        
        m = re.search(regexp, fix_msg)
        if m is None:
            raise MessageError("The message is not fix type")
        self.type = m.group(1)
        self.issue = m.group(2)
        issue_pattern = 'T<([^>]*)>\s(.*)'
        m_issue = re.search(issue_pattern, self.issue)
        if m_issue is not None:
            self.issue_short = m_issue.group(1)
            self.issue = m_issue.group(2)
        else:
            self.issue_short = None
        self.fix = m.group(3)
        self.fun1 = m.group(4)
        file1 = m.group(5)
        self.fun2 = m.group(6)
        file2 = m.group(7)
        self.file1_name = os.path.basename(file1) 
        self.file1_link = file1.replace(
            '/Users/afshin/Documents/work/VerifyDicom',
            git_url.format('tree/' + commit))
        self.file2_name = os.path.basename(file2) 
        self.file2_link = file2.replace(
            '/Users/afshin/Documents/work/VerifyDicom',
            git_url.format('tree/' + commit))
        element_pattern = '(Element|attribute|keyword)[=\s]{,5}<([^>]*)>'
        m = re.search(element_pattern, fix_msg)
        if m is not None:
            self.attribute = m.group(2)
        else:
            self.attribute = None
        if self.attribute is not None:
            self.tag = Dic.tag_for_keyword(self.attribute)
        else:
            ptrn = '\(0x([0-9A-Fa-f]{4})[,\s]0x([0-9A-Fa-f]{4})\)'
            m =  re.search(ptrn, fix_msg)
            if m is not None:
                self.tag = int(m.group(1) + m.group(2), 16)
            else:
                self.tag = None


        module_pattern = '(Module|Macro)[=\s]{,5}<([^>]*)>'
        m = re.search(module_pattern, fix_msg)
        if m is not None:
            self.module_macro = m.group(2)
        else:
            self.module_macro = None

    def GetQuery(self, SOPInstanceUID: uid) -> str:
        out = '''(
                    {}, -- DCM_SOP_INSATANCE_UID 
                    {}, -- SHORT_ISSUE 
                    {}, -- ISSUE 
                    {}, -- FIX 
                    {}, -- TYPE 
                    {}, -- MODULE_MACRO 
                    {}, -- KEYWORD 
                    {}, -- TAG 
                    {}, -- FIX_FUNCTION1 
                    {}, -- FIX_FUNCTION2 
                    {} -- MESSAGE 
            )
            '''.format(
                self.GetValue(str(SOPInstanceUID)),
                self.GetValue(self.issue_short),
                self.GetValue(self.issue),
                self.GetValue(self.fix),
                self.GetValue(self.type),
                self.GetValue(self.module_macro),
                self.GetValue(self.attribute),
                self.GetValue(self.tag),
                self.GetValue(self.file1_link),
                self.GetValue(self.file2_link),
                self.GetValue(self.message),
                )
        return out

    def GetQuery_OLD(self, SOPInstanceUID: uid) -> str:
        out = '''
            CALL `{{0}}`.ADD_TO_FIX(
                {},  --SHORT_ISSUE
                {},  --ISSUE
                {},  --FIX
                {},  --TYPE
                {},  --MODULE_MACRO
                {},  --KEYWORD
                {},   --TAG
                {},  --FIX_FUNCTION1
                {},  --FIX_FUNCTION2
                {},  --MESSAGE
                {},  --SOP_INST_UID
                ID   --ID
            );
            '''.format(
                self.GetValue(self.issue_short),
                self.GetValue(self.issue),
                self.GetValue(self.fix),
                self.GetValue(self.type),
                self.GetValue(self.module_macro),
                self.GetValue(self.attribute),
                self.GetValue(self.tag),
                self.GetValue(self.file1_link),
                self.GetValue(self.file2_link),
                self.GetValue(self.message),
                self.GetValue(str(SOPInstanceUID))
            )
        return out

    def GetValue(self, v):
        if v is None:
            return "NULL"
        elif type(v) == str:
            return '"{}"'.format(v)
        else:
            return v


class FixCollection:

    def __init__(self, fixes: list, dcmfile:str) -> None:
        try: 
            ds = pydicom.read_file(dcmfile, specific_tags = ['SOPInstanceUID'])
            self.SOPInstanceUID = ds['SOPInstanceUID'].value
        except BaseException:
            self.SOPInstanceUID = None
        self.fixes: list = []
        for fix in fixes:
            try:
                self.fixes.append(DicomFix(fix))
            except MessageError:
                pass
    
    def GetQueryHeader(self) -> str:
        header = '''
            INSERT INTO `{0}`.FIX
                VALUES {1};
        '''
        return header

    def GetQuery(self) -> str:
        q = []
        for i, f in enumerate(self.fixes):
            q.append(f.GetQuery(self.SOPInstanceUID))
        return q

class FileUIDS:

    def __init__(self, file, vfile, mfile):
        try:
            ds = pydicom.read_file(file, specific_tags = [
                'SOPInstanceUID','SOPClassUID', 'StudyInstanceUID',
                'SeriesInstanceUID'
            ])
            self.SOPInstanceUID = ds['SOPInstanceUID'].value
            self.StudyUID = ds['StudyInstanceUID'].value
            self.SeriesUID = ds['SeriesInstanceUID'].value
            self.SOPClassUID = ds['SOPClassUID'].value
            self.SOPClassTxt =\
                single2multi_frame.SopClassUID2Txt(self.SOPClassUID)
            self.VerificationFilePath = vfile
            self.MetaFilePath = mfile
        except BaseException as err:
            print(err)
            self.SOPInstanceUID = ''
            self.StudyUID = ''
            self.SeriesUID = ''


def VER(file:str, log:list):
    file_name = os.path.basename(file)
    if file_name.endswith('.dcm'):
        file_name = file_name[:-4]
    dcm_verify = "/Users/afshin/Documents/softwares"\
        "/dicom3tools/exe_20200430/dciodvfy"
    if not os.path.exists(dcm_verify):
        dcm_verify = shutil.which('dciodvfy')
        if dcm_verify is None:
            print("Error: install dciodvfy into system path")
            assert(False)
    ctools.RunExe([dcm_verify,'-filename', file], '', '', errlog = log)
    my_code_output = verify(file, False, '')
    
# == == == == == == == == == == == == == == == == == == == == == == == == == 


def FixFile(dicom_file, in_folder, 
            fixed_dcm_folder,
            log_fix, log_david_pre, log_david_post):
    # ------------------------------------------------------------------
    deslash = lambda x: x if not x.endswith('/') else x[:-1]
    parent = os.path.dirname(dicom_file)
    file_name = os.path.basename(dicom_file)

    in_folder = deslash(in_folder)
    # ------------------------------------------------------------------
    f_dcm_folder = parent.replace(in_folder, fixed_dcm_folder)
    if not os.path.exists(f_dcm_folder):
        os.makedirs(f_dcm_folder)
    ds = read_file(dicom_file)
    log_mine = []
    (v_file_pre, m_file_pre) = VER(dicom_file, log_david_pre)
    fix_frequent_errors.priorfix_RemoveIllegalTags(ds,'All', log_fix)
    #(1)general fixes:
    for ffix in dir(fix_frequent_errors):
        if ffix.startswith("generalfix_"):
            item = getattr(fix_frequent_errors, ffix)
            if callable(item):
                item(ds, log_fix)
    #(2)fix with verification:
    fix_Trivials(ds, log_fix)
    #(3)specific fixes:
    for ffix in dir(fix_frequent_errors):
        if ffix.startswith("fix_"):
            if ffix == "fix_Trivials":
                continue
            item = getattr(fix_frequent_errors, ffix)
            if callable(item):
                item(ds, log_fix)
    fix_report = PrintLog(log_fix)
    (v_file_post, m_file_post) = VER(fixed_file,
                                     log_david_post)

def BuildQueries(header:str, qs:list, dataset_id: str) -> list:
    out_q = []
    ch_limit = 1024*1024
    row_limit = 1500
    elem_q = ''
    n = 0
    rn = 0
    for q in qs:
        rn += 1
        if len(elem_q) + len(q) + len(header) < ch_limit and rn < row_limit:
            elem_q = q if elem_q == '' else '{},{}'.format(q, elem_q) 
        else:
            n += 1
            out_q.append(header.format(dataset_id, elem_q))
            elem_q = ''
            rn = 0
            print('{} ->'.format(n))
            query_string(out_q[-1])
    return out_q

        


def FIX_AND_CONVERT(in_folder, out_folder, prefix =''):
    dcm_folder = os.path.join(out_folder, "fixed_dicom/")
    mfdcm_folder = os.path.join(out_folder, "multiframe/")
    
    input_table = 'InputTable'
    fixed_table = 'FixedTable'
    mf_table = 'MultiFrameTable'
    dataset_id = '{}.{}'.format(PROJECT_NAME, dataset)
    print(in_folder)
    if not os.path.exists(in_folder):
        return
    folder_list = ctools.Find(in_folder, cond_function=ctools.is_dicom, find_parent_folder=True)
    start = time.time()
    repo = git.Repo(search_parent_directories=True)
    print(repo.active_branch)
    sha = repo.head.object.hexsha
    print(sha)
    time_interval_for_progress_update = 1
    time_interval_record_data = 1800
    last_time_point_for_progress_update = 0
    last_time_point_record_data = 0
    analysis_started = False
    q_fix_string = []
    q_issue_string = []
    q_origin_string = []
    for i, folder in enumerate(folder_list, 1):
        progress = float(i) / float(len(folder_list))
        time_point = time.time()
        time_elapsed = round(time_point - start)
        time_left = round(float(len(folder_list)-i) * time_elapsed/float(i))
        time_elapsed_since_last_show = (time_point -
            last_time_point_for_progress_update)
        time_elapsed_since_last_record = (time_point -
            last_time_point_record_data)

        in_files = ctools.Find(in_folder, 1, ctools.is_dicom)
        for f in in_files:
            log_david_post = []
            log_david_pre = []
            log_fixed = []
            (v_pre, m_pre, v_post, m_post) = FixFile(
                f, in_folder, dcm_folder,
                fix_folder, log_fixed,
                log_david_pre, log_david_post)
            fixed_file_path = f.replace(in_folder, dcm_folder)
            fixes_all = FixCollection(log_fixed, f)
            q_fix_string.extend(fixes_all.GetQuery())
            pre_issues = IssueCollection(log_david_pre[1:], input_table, f)
            q_issue_string.extend(pre_issues.GetQuery())
            post_issues = IssueCollection(log_david_post[1:], fixed_table, 
                f.replace(in_folder, dcm_folder))
            q_issue_string.extend(post_issues.GetQuery())
            fixed_input_ref = conv.ParentChildDicoms(pre_issues.SOPInstanceUID,
                                   post_issues.SOPInstanceUID,
                                   f.replace(in_folder, dcm_folder))
            q_origin_string.extend(fixed_input_ref.GetQuery(input_table, fixed_table))
        #  -------------------------------------------------------------
        mf_log:list = []
        single_fixed_folder = folder.replace(in_folder, dcm_folder)
        mf_folder = folder.replace(in_folder, mfdcm_folder)
        if not os.path.exists(mf_folder):
            os.makedirs(mf_folder)
        # try:
        PrntChld = conv.ConvertByHighDicomNew(
            single_fixed_folder, mf_folder, mf_log)
        # except(BaseException) as err:
        #     mf_log.append(str(err))
        #     PrntChld = []
        for pr_ch in PrntChld:
            #query_string(pr_ch.GetQuery(fixed_table, mf_table).format(
                # dataset_id))
            q_origin_string.extend(pr_ch.GetQuery(input_table, fixed_table))
            multiframe_log = []

            (v_file_post, m_file_post) = VER(pr_ch.child_dicom_file,
                                        mfvfy_folder,
                                        multiframe_log)
            mf_issues = IssueCollection(multiframe_log[1:], mf_table, 
                pr_ch.child_dicom_file)
            q_issue_string.extend(mf_issues.GetQuery())
            
            #query_string(mf_issues.GetQuery().format(dataset_id))
        if time_elapsed_since_last_show > time_interval_for_progress_update:
            last_time_point_for_progress_update = time_point
            ctools.ShowProgress(progress, time_elapsed, time_left, 80, prefix)
            if i == len(folder_list):
                print('\n')
    fix_header = fixes_all.GetQueryHeader()
    issue_header = mf_issues.GetQueryHeader()
    origin_header = PrntChld[0].GetQueryHeader()
    file_name = './gitexcluded_qqq.txt'
    ctools.WriteStringToFile(file_name, ctools.StrList2Txt(BuildQueries(fix_header, q_fix_string, dataset_id)))
    ctools.WriteStringToFile(file_name, ctools.StrList2Txt(BuildQueries(issue_header, q_issue_string, dataset_id)), True)
    ctools.WriteStringToFile(file_name, ctools.StrList2Txt(BuildQueries(origin_header, q_origin_string, dataset_id)), True)
    return(
        pre_fix_error_statistics, 
        post_fix_error_statistics,
        pre_fix_warning_statistics, 
        post_fix_warning_statistics
        )

def CreateDicomStore(project_id: str,
                     cloud_region: str,
                     dataset_id: str,
                     diocm_store_id:str):
    if not exists_dataset(project_id, cloud_region, dataset_id):
        create_dataset(project_id, cloud_region, dataset_id)
    if not exists_dicom_store(project_id, 
                       cloud_region, dataset_id, 
                       dicom_store_id):
        create_dicom_store(project_id, cloud_region, dataset_id, dicom_store_id)

# create_all_tables('{}.{}'.format(PROJECT_NAME, dataset), True)
small = 'TCGA-UCEC/TCGA-D1-A16G/07-11-1992-NMPETCT trunk-82660/'\
    '1005-TRANSAXIALTORSO 3DFDGIR CTAC-37181/'
# small = ''
home = os.path.expanduser("~")
local_tmp_folder = os.path.join(home,"Tmp")
# if os.path.exists(local_tmp_folder):
#     shutil.rmtree(local_tmp_folder)
# os.makedirs(local_tmp_folder)

out_folder = os.path.join(local_tmp_folder,"bgq_output")
in_folder = os.path.join(local_tmp_folder,"bgq_input")
# in_folder = os.path.join(local_tmp_folder,"IDC-MF_DICOM/data/"+small)

# bucket_address = ''
# project_id = 'idc-tcia'
# cloud_region = 'us'
# dicom_store_dataset_id = 'afshin-dataset-test01'
# dicom_store_id = 'dicom-store-test01'
# content_uri = 'afshin-test/t/13-Perfusion-59033/*.dcm'
# bigquery_dataset = 'afshin_test00'
# bigquery_table_id = 'INPUT'
# uri_prefix = '`{}.{}.{}`'.format(project_id, bigquery_dataset, bigquery_table_id )
# in_dicoms = DataInfo(
#     'idc-dev-etl',
#     'us-central1',
#     '',
#     'idc_tcia_mvp_wave0',
#     'idc_tcia',
#     'idc_tcia_mvp_wave0',
#     'idc_tcia_dicom_metadata'
#     )
# fx_dicoms = DataInfo(
#     'idc-tcia',
#     'us-central1',
#     '',
#     'afshin-results' + in_dicoms.DicomStoreDataset,
#     'FIXED',
#     'afshin-results' + in_dicoms.DicomStoreDataset,
#     'FIXED'
#     )
# mf_dicoms = DataInfo(
#     'idc-tcia',
#     'us-central1',
#     '',
#     'afshin-results' + in_dicoms.DicomStoreDataset,
#     'MULTIFRAME',
#     'afshin-results' + in_dicoms.DicomStoreDataset,
#     'MULTIFRAME'
#     )
# CreateDicomStore(
#     fx_dicoms.ProjectID,
#     fx_dicoms.CloudRegion,
#     fx_dicoms.DicomStoreDataset,
#     fx_dicoms.DicomStore)
# CreateDicomStore(
#     mf_dicoms.ProjectID,
#     mf_dicoms.CloudRegion,
#     mf_dicoms.DicomStoreDataset,
#     mf_dicoms.DicomStore)

# # import_dicom_instance(project_id, cloud_region, dicom_store_dataset_id,
# #                       dicom_store_id, content_uri)
# # export_dicom_instance_bigquery(project_id, cloud_region, dicom_store_dataset_id,
# #                       dicom_store_id, uri_prefix)
# study_query = 'SELECT STUDYINSTANCEUID, SERIESINSTANCEUID, SOPINSTANCEUID FROM `{0}` ORDER BY STUDYINSTANCEUID, SERIESINSTANCEUID, SOPINSTANCEUID'
# uids: dict = {}
# q_dataset_uid = '{}.{}.{}'.format(
#     in_dicoms.ProjectID,
#     in_dicoms.BigQueryDataset,
#     in_dicoms.BigQueryTable
#     )
# max_number_of_instances = 2
# max_number_of_series = 2
# max_number_of_studies = 2
# studies = query_string_with_result(study_query.format(q_dataset_uid))
# if studies is not None:
#     for row in studies:
#         stuid = row.STUDYINSTANCEUID
#         seuid = row.SERIESINSTANCEUID
#         sopuid = row.SOPINSTANCEUID
#         if stuid in uids:
#             if seuid in uids[stuid]:
#                 uids[stuid][seuid].append(sopuid)
#             else:
#                 uids[stuid][seuid] = [sopuid]
#         else:
#             uids[stuid] = {seuid: [sopuid]}
#     for number_of_studies, (study_uid, sub_study) in enumerate(uids.items()):
#         if number_of_studies > max_number_of_studies:
#             break
#         for number_of_series, (series_uid, instances) in enumerate(sub_study.items()):
#             if number_of_series > max_number_of_series:
#                 break
#             number_of_instances = 0
#             for instance_uid in instances:
#                 destination_file = os.path.join(
#                     in_folder, '{}/{}/{}.dcm'.format(
#                         study_uid, series_uid, instance_uid
#                     )
#                 )
#                 dicomweb_retrieve_instance(
#                     _BASE_URL, in_dicoms.ProjectID, in_dicoms.CloudRegion,
#                     in_dicoms.DicomStoreDataset, in_dicoms.DicomStore,
#                     study_uid, series_uid, instance_uid, destination_file)
#                 number_of_instances += 1
#                 if number_of_instances > max_number_of_instances:
#                     break
study_uids = os.listdir(in_folder)
for study_uid in study_uids:
    input_stats = FIX_AND_CONVERT(os.path.join(
        in_folder, '/{}'.format(study_uid)), out_folder, 'INPUT FIX')
        


# print(uids)
# d_list = list_dicom_stores('idc-tcia', 'us', 'issues')
# if len(sys.argv) > 1:
#     in_folder = sys.argv[1]
# if os.path.exists(out_folder):
#     shutil.rmtree(out_folder)
# slash = lambda x: x if x.endswith('/') else x+'/'
# in_folder = slash(in_folder)
# out_folder = slash(out_folder)
# # ---------------------------------------------------------------
# highdicom_folder = os.path.join(out_folder, "hd/files")
# pixelmed_folder = os.path.join(out_folder, "pm/files")
# inputresult_folder = os.path.join(out_folder,"in")
# input_stats = FIX_AND_CONVERT(in_folder, inputresult_folder, 'INPUT FIX')
# fixed_folder = os.path.join(inputresult_folder, 'fixed_dicom/')
# conversion_log = []
# single2multi_frame.Convert(fixed_folder, pixelmed_folder, highdicom_folder,
#      conversion_log)
# ctools.WriteStringToFile(os.path.join(highdicom_folder,'highdicom_log.txt'),
# ctools.StrList2Txt(conversion_log))
# hd_stats = FIX(highdicom_folder, os.path.dirname(highdicom_folder), 'FIXING HD')
# pm_stats = FIX(pixelmed_folder, os.path.dirname(pixelmed_folder), 'FIXING PM')
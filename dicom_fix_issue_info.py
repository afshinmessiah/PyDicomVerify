import git
import pydicom.datadict as Dic
from pydicom.multival import MultiValue
from pydicom import uid
import re
import os
from typing import List
import common.common_tools as ct
from datetime import timedelta
from pydicom import Dataset
from pydicom.charset import python_encoding
from gcloud.BigQueryStuff import *
git_url = 'https://github.com/afshinmessiah/PyDicomVerify/{}'
repo = git.Repo(search_parent_directories=True)
commit = repo.head.object.hexsha
iod_names = [
        "CRImage",
        "CTImage",
        "MRImage",
        "NMImage",
        "USImage",
        "USMultiFrameImage",
        "SCImage",
        "MultiframeSingleBitSCImage",
        "MultiframeGrayscaleByteSCImage",
        "MultiframeGrayscaleWordSCImage",
        "MultiframeTrueColorSCImage",
        "StandaloneOverlay",
        "StandaloneCurve",
        "StandaloneModalityLUT",
        "StandaloneVOILUT",
        "Segmentation",
        "SurfaceSegmentation",
        "SpatialRegistration",
        "DeformableSpatialRegistration",
        "SpatialFiducials",
        "EncapsulatedPDF",
        "EncapsulatedCDA",
        "EncapsulatedSTL",
        "RealWorldValueMapping",
        "IVOCTImage",
        "ParametricMap",
        "BasicDirectory",
        "BasicDirectoryDental",
        "XAImage",
        "XRFImage",
        "EnhancedXAImage",
        "EnhancedXRFImage",
        "XRay3DAngiographicImage",
        "XRay3DCraniofacialImage",
        "PETImage",
        "EnhancedPETImage",
        "LegacyConvertedEnhancedPETImage",
        "PrivatePixelMedLegacyConvertedEnhancedPETImage",
        "RTImage",
        "RTDose",
        "RTStructureSet",
        "RTPlan",
        "RTBeamsTreatmentRecord",
        "RTBrachyTreatmentRecord",
        "RTTreatmentSummaryRecord",
        "RTIonPlan",
        "RTIonBeamsTreatmentRecord",
        "DXImageForProcessing",
        "DXImageForPresentation",
        "MammographyImageForProcessing",
        "MammographyImageForPresentation",
        "MammographyImageForProcessingIHEMammo",
        "MammographyImageForProcessingIHEMammoPartialViewOption",
        "MammographyImageForPresentationIHEMammo",
        "MammographyImageForPresentationIHEMammoPartialViewOption",
        "IntraoralImageForProcessing",
        "IntraoralImageForPresentation",
        "IntraoralImageForPresentationDentalMedia",
        "DXImageForPresentationDentalMedia",
        "BreastTomosynthesisImage",
        "BreastTomosynthesisImageIHEDBT",
        "BreastProjectionXRayImage",
        "VLEndoscopicImage",
        "VLMicroscopicImage",
        "VLSlideCoordinatesMicroscopicImage",
        "VLPhotographicImage",
        "VideoEndoscopicImage",
        "VideoMicroscopicImage",
        "VideoPhotographicImage",
        "OphthalmicPhotography8BitImage",
        "OphthalmicPhotography16BitImage",
        "StereometricRelationship",
        "OphthalmicTomographyImage",
        "VLWholeSlideMicroscopyImage",
        "LensometryMeasurements",
        "AutorefractionMeasurements",
        "KeratometryMeasurements",
        "SubjectiveRefractionMeasurements",
        "VisualAcuityMeasurements",
        "OphthalmicAxialMeasurements",
        "IntraocularLensCalculations",
        "OphthalmicVisualFieldStaticPerimetryMeasurements",
        "BasicVoice",
        "TwelveLeadECG",
        "GeneralECG",
        "AmbulatoryECG",
        "HemodynamicWaveform",
        "CardiacElectrophysiologyWaveform",
        "BasicTextSR",
        "EnhancedSR",
        "ComprehensiveSR",
        "Comprehensive3DSR",
        "KeyObjectSelectionDocument",
        "KeyObjectSelectionDocumentIHEXDSIManifest",
        "MammographyCADSR",
        "ChestCADSR",
        "ProcedureLog",
        "XRayRadiationDoseSR",
        "XRayRadiationDoseSRIHEREM",
        "RadiopharmaceuticalRadiationDoseSR",
        "SpectaclePrescriptionReport",
        "AcquisitionContextSR",
        "GrayscaleSoftcopyPresentationState",
        "ColorSoftcopyPresentationState",
        "PseudoColorSoftcopyPresentationState",
        "BlendingSoftcopyPresentationState",
        "HangingProtocol",
        "ColorPalette",
        "BasicStructuredDisplay",
        "EnhancedMRImage",
        "EnhancedMRColorImage",
        "MRSpectroscopy",
        "RawData",
        "LegacyConvertedEnhancedMRImage",
        "PrivatePixelMedLegacyConvertedEnhancedMRImage",
        "TractographyResults",
        "EnhancedCTImage",
        "LegacyConvertedEnhancedCTImage",
        "PrivatePixelMedLegacyConvertedEnhancedCTImage",
        "EnhancedUltrasoundVolume",
        "EnhancedUltrasoundVolumeQTUS",
    ]

def organize_dcmvfy_errors(issues: list, output: list = []):
    prev_line = None
    for line_ in issues:
        if line_ in iod_names:
            continue
        if line_.startswith('Error - ') or line_.startswith('Warning - '):
            if prev_line is not None:
                output.append(prev_line)
            prev_line = line_
        else:
            if prev_line is not None:
                prev_line += ('\n' + line_)
    if prev_line is not None:
        output.append(prev_line)


class Datalet:

    def __init__(self, project_id: str,
                 cloud_region: str,
                 dataset: str,
                 dataobject: str):
        self.ProjectID = project_id
        self.CloudRegion = cloud_region
        self.Dataset = dataset
        self.DataObject = dataobject

    def GetBigQueryStyleTableAddress(self, quoted: bool = True) -> str:
        output = '{}.{}'.format(
            self.ProjectID,
            self.Dataset
        )
        if quoted:
            output = '`{}`.{}'.format(output, self.DataObject)
        else:
            output = '{}.{}'.format(output, self.DataObject)

        return output

    def GetBigQueryStyleDatasetAddress(self, quoted: bool = True) -> str:
        output = '{}.{}'.format(
            self.ProjectID,
            self.Dataset
        )
        if quoted:
            output = '`{}`'.format(output)
        return output


class DataInfo:

    def __init__(self, bucket_datalet: Datalet,
                 dicomstore_datalet: Datalet,
                 bigquery_datalet: Datalet):
        self.Bucket = bucket_datalet
        self.DicomStore = dicomstore_datalet
        self.BigQuery = bigquery_datalet


class MessageError(Exception):

    def __init__(self, original_msg: str):
        self.original_message = original_msg
        self.message = \
            "Message <{}> doesn't have an appropriate format".format(
                self.original_message
                )
        super().__init__(self.message)


class table_quota:
    def __init__(self, quota: int, table_base_id: str, schema: list):
        self.table_id_number: int = 0
        self.table_update_counter: int = 0
        self.table_update_quota_limit: int = quota
        self._schema = schema
        self._table_base_id = table_base_id

    def get_table(self):
        if self.table_update_counter == 0 and self.table_id_number == 0:
            create_new = True
        else:
            create_new = False
        self.table_update_counter += 1
        create_new: bool = False
        if self.table_update_counter > \
                self.table_update_quota_limit:
            self.table_update_counter %=\
                self.table_update_quota_limit
            self.table_id_number += 1
            create_new = True
        real_table = "{}_{:03d}".format(
            self._table_base_id, self.table_id_number)
        if create_new:
            create_table(real_table, self._schema)
        return real_table
    
    
    
    @property
    def schema(self):
        return self._schema

    @property
    def table_base_id(self):
        return self._table_base_id


class DicomIssue:

    def __init__(self, issue_msg: str) -> None:
        self.message = issue_msg
        regexp = r'.*(Error|Warning)([-\s]*)(.*)'
        m = re.search(regexp, issue_msg)
        if m is None:
            raise MessageError('The issue is not a right type')
        self.type = m.group(1)
        self.issue_msg = m.group(3)
        issue_pattern = r'T<([^>]*)>\s(.*)'
        m_issue = re.search(issue_pattern, self.issue_msg)
        if m_issue is not None:
            self.issue_short = m_issue.group(1)
            self.issue = m_issue.group(2)
        else:
            self.issue_short = None
        element_pattern = r'(Element|attribute|keyword)[=\s]{,5}<([^>]*)>'
        m = re.search(element_pattern, issue_msg)
        if m is not None:
            self.attribute = m.group(2)
        else:
            self.attribute = None
        if self.attribute is not None:
            self.tag = Dic.tag_for_keyword(self.attribute)
        else:
            ptrn = r"\(0x([0-9A-Fa-f]{4})[,\s]*0x([0-9A-Fa-f]{4})\)"
            m =  re.search(ptrn, issue_msg)
            if m is not None:
                self.tag = int(m.group(1) + m.group(2), 16)
            else:
                self.tag = None
        module_pattern = r'(Module|Macro)[=\s]{,5}<([^>]*)>'
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
        out1 = (
                TableName,  # DCM_TABLE_NAME
                str(SOPInstanceUID),  # DCM_SOP_INSATANCE_UID
                self.issue_msg,  # ISSUE_MSG
                self.message,  # MESSAGE
                self.type,  # TYPE
                self.module_macro,  # MODULE_MACRO
                self.attribute,  # KEYWORD
                self.tag,  # TAG
        )
        return (out, out1)

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
            return '"""{}"""'.format(v)
        else:
            return v


class IssueCollection:

    def __init__(self, issues: list, table_name: str,
                 study_uid: str,
                 series_uid: str,
                 sop_uid: str
                 ) -> None:
        self.table_name = table_name
        self.StudyInstanceUID = study_uid
        self.SeriesInstanceUID = series_uid
        self.SOPInstanceUID = sop_uid
        self.issues: list = []
        for issue in issues:
            try:
                self.issues.append(DicomIssue(issue))
            except BaseException:
                pass

    @staticmethod
    def GetQueryHeader() -> str:
        header = '''
            INSERT INTO `{0}`.ISSUE
                VALUES {1}
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
        regexp = r'([^-]*)\s-\s(.*):-\>:(.*)\<function(.*)from file:(.*) line_number: (.*)\> \<function(.*)from file:(.*) line_number: (.*)\>'
        m = re.search(regexp, fix_msg)
        if m is None:
            raise MessageError("The message is not fix type")
        self.type = m.group(1)
        self.issue = m.group(2)
        issue_pattern = r'T<([^>]*)>\s(.*)'
        m_issue = re.search(issue_pattern, self.issue)
        if m_issue is not None:
            self.issue_short = m_issue.group(1)
            self.issue = m_issue.group(2)
        else:
            self.issue_short = None
        self.fix = m.group(3)
        self.fun1 = m.group(4)
        file1 = m.group(5)
        line1 = m.group(6)
        self.fun2 = m.group(7)
        file2 = m.group(8)
        line2 = m.group(9)
        self.file1_name = os.path.basename(file1)
        self.file1_link = git_url.format('tree/' + commit) + "/{}#L{}".format(
            self.file1_name, line1)
        self.file2_name = os.path.basename(file2)
        self.file2_link = git_url.format('tree/' + commit) + "/{}#L{}".format(
            self.file2_name, line2)
        element_pattern = r'(Element|attribute|keyword)[=\s]{,5}<([^>]*)>'
        m = re.search(element_pattern, self.issue)
        if m is not None:
            self.attribute = m.group(2)
        else:
            self.attribute = None
        if self.attribute is not None:
            self.tag = Dic.tag_for_keyword(self.attribute)
        else:
            ptrn = r'\(0x([0-9A-Fa-f]{4})[,\s]{,2}0x([0-9A-Fa-f]{4})\)'
            m =  re.search(ptrn, self.issue)
            if m is not None:
                self.tag = int(m.group(1) + m.group(2), 16)
            else:
                self.tag = None
        module_pattern = r'(Module|Macro)[=\s]{,5}<([^>]*)>'
        m = re.search(module_pattern, self.issue)
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
                    {}, -- FIX_FUNCTION1_LINK
                    {}, -- FIX_FUNCTION2
                    {}, -- FIX_FUNCTION2_LINK
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
                self.GetValue(self.fun1),
                self.GetValue(self.file1_link),
                self.GetValue(self.fun2),
                self.GetValue(self.file2_link),
                self.GetValue(self.message),
                )
        out1 = (
            str(SOPInstanceUID),  # DCM_SOP_INSATANCE_UID
            self.issue_short,  # SHORT_ISSUE
            self.issue,  # ISSUE
            self.fix,  # FIX
            self.type,  # TYPE
            self.module_macro,  # MODULE_MACRO
            self.attribute,  # KEYWORD
            self.tag,  # TAG
            self.fun1,  # FIX_FUNCTION1
            self.file1_link,  # FIX_FUNCTION1_LINK
            self.fun2,  # FIX_FUNCTION2
            self.file2_link,  # FIX_FUNCTION2_LINK
            self.message,   # MESSAGE
        )
        return (out, out1)

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
            return '"""{}"""'.format(v)
        else:
            return v


class FixCollection:

    def __init__(self, fixes: list,
                 study_uid: str,
                 series_uid: str,
                 sop_uid: str
                 ) -> None:
        self.StudyInstanceUID = study_uid
        self.SeriesInstanceUID = series_uid
        self.SOPInstanceUID = sop_uid
        self.fixes: list = []
        for fix in fixes:
            try:
                self.fixes.append(DicomFix(fix))
            except MessageError:
                pass

    @staticmethod
    def GetQueryHeader(table_name) -> str:
        header = '''
            INSERT INTO `{0}`.{}
                VALUES {1};
        '''.format(table_name)
        return header

    def GetQuery(self) -> str:
        q = []
        for i, f in enumerate(self.fixes):
            q.append(f.GetQuery(self.SOPInstanceUID))
        return q


class DicomFileInfo:
    def __init__(self,
                 project_id: str,
                 bucket_name: str,
                 blob_address: str,
                 file_path: str,
                 study_uid: str,
                 series_uid: str,
                 instance_uid: str,
                 dicom_dataset: Dataset = None):
        self.project_id = project_id
        self.bucket_name = bucket_name
        self.blob_address = blob_address
        self.file_path = file_path
        self.study_uid = study_uid
        self.series_uid = series_uid
        self.instance_uid = instance_uid
        self.dicom_ds = dicom_dataset
        

    def __str__(self):
        out = 'DicomFileInfo\n{{\n{}\n}}'
        content = ''
        content += '\n\t\t {} = {}'.format("project_id", self.project_id)
        content += '\n\t\t {} = {}'.format("bucket_name", self.bucket_name)
        content += '\n\t\t {} = {}'.format("blob_address", self.blob_address)
        content += '\n\t\t {} = {}'.format("file_path", self.file_path)
        content += '\n\t\t {} = {}'.format("study_uid", self.study_uid)
        content += '\n\t\t {} = {}'.format("series_uid", self.series_uid)
        content += '\n\t\t {} = {}'.format("instance_uid", self.instance_uid)
        content += '\n\t\t {} = {}'.format(
            "dicom_ds", self.dicom_ds if
            self.dicom_ds is None else 'Exists but hidden')
        return out.format(content)

    @staticmethod
    def get_chaset_val_from_dataset(ds: Dataset = None) -> str:
        python_char_set = 'ascii'
        if isinstance(ds, Dataset) and ds is not None:
            if "SpecificCharacterSet" in ds:
                dicom_char_set = ds.SpecificCharacterSet
                if isinstance(dicom_char_set, MultiValue):
                    dicom_char_set = dicom_char_set[-1]
                if isinstance(dicom_char_set, str):
                    if dicom_char_set in python_encoding:
                        python_char_set = python_encoding[dicom_char_set]
        return python_char_set



class PerformanceMeasure:

    def __init__(self, size_: float, time_in_sec: int,
                 suffix: str='', binary: bool=True):
        self.size = size_
        self.time_in_sec = time_in_sec
        self.suffix = suffix
        self.binary = binary

    def __add__(self, other):
        sz = self.size + other.size
        tm = self.time_in_sec + other.time_in_sec
        return PerformanceMeasure(sz, tm)
    
    def __iadd__(self, other):
        self.size += other.size
        self.time_in_sec += other.time_in_sec
        return self

    def __str__(self):
        if self.time_in_sec > 10:
            time = int(self.time_in_sec)
        else:
            time = self.time_in_sec
        e_t = timedelta(seconds=time)
        if self.suffix == '(inst)':
            sz = str(self.size)
        else:
            sz = ct.get_human_readable_string(self.size, self.binary)
        speed = 0 if self.time_in_sec == 0 else (self.size / self.time_in_sec)
        rate = ct.get_human_readable_string(speed)
        output = '{1}{0:8.8s} in {2:24.24s} ({3}{4:12.12s})'.format(
            self.suffix, sz, str(e_t), rate, self.suffix + '/sec')
        return output


class ProcessPerformance:

    def __init__(self, down: PerformanceMeasure = PerformanceMeasure(0, 0),
                 up: PerformanceMeasure = PerformanceMeasure(0, 0),
                 fx_: PerformanceMeasure = PerformanceMeasure(0, 0),
                 fr_: PerformanceMeasure = PerformanceMeasure(0, 0),
                 cn_: PerformanceMeasure = PerformanceMeasure(0, 0),
                 bq: PerformanceMeasure = PerformanceMeasure(0, 0)
                 ):
        self.download: PerformanceMeasure = down
        self.upload: PerformanceMeasure = up
        self.fix: PerformanceMeasure = fx_
        self.frameset: PerformanceMeasure = fr_
        self.convert: PerformanceMeasure = cn_
        self.bigquery: PerformanceMeasure = bq
        # self.download.suffix = 'B'
        # self.upload.suffix = 'B'
        # self.bigquery.suffix = '(row)'
        # self.fix.suffix = '(inst)'
        # self.convert.suffix = '(multiframe-inst'
        # self.frameset.suffix = '(frameset-inst'

    def __add__(self, other):
        download = self.download + other.download
        upload = self.upload + other.upload
        fix = self.fix + other.fix
        frameset = self.frameset + other.frameset
        convert = self.convert + other.convert
        bigquery = self.bigquery + other.bigquery
        return ProcessPerformance(
            download, upload, fix, frameset, convert, bigquery)

    def __iadd__(self, other):
        self.download += other.download
        self.upload += other.upload
        self.fix += other.fix
        self.convert += other.convert
        self.frameset += other.frameset
        self.bigquery += other.bigquery
        return self

    @property
    def entire_time(self):
        return (self.download.time_in_sec +
                self.upload.time_in_sec +
                self.fix.time_in_sec +
                self.convert.time_in_sec +
                self.frameset.time_in_sec +
                self.bigquery.time_in_sec)

    def __str__(self):
        t_time = self.entire_time
        if t_time == 0:
            t_time = 1
        form = 'download -> {} [{:.1%}]\tupload -> {} [{:.1%}]\t'\
            'fix -> {} [{:.1%}]\t'\
            'frameset extraction-> {} [{:.1%}]\t'\
            'conversion -> {} [{:.1%}]\tbig query -> {} [{:.1%}]'
        return form.format(str(self.download),
                           self.download.time_in_sec / t_time,
                           str(self.upload),
                           self.upload.time_in_sec / t_time,
                           str(self.fix),
                           self.fix.time_in_sec / t_time,
                           str(self.frameset),
                           self.frameset.time_in_sec / t_time,
                           str(self.convert),
                           self.convert.time_in_sec / t_time,
                           str(self.bigquery),
                           self.bigquery.time_in_sec / t_time,
                           )

# module.awk Copyright (c) 1993-2018, David A. Clunie DBA PixelMed Publishing. All rights reserved.
# create C++ headers from rightdicom.dcmvfy.modules template 

# can set these values on the command line:
#


function indentcode(count)
{
	if (count) {
		#count=count;
		while (count-- > 0) {
			printf("\t")
		}
	}
}

function indentforwrite(count)
{
	if (count) {
		indentcode(count)
		printf("\tstream << \"")
		while (count-- > 0) {
			printf("\\t")
		}
		printf("\";\n")
	}
}
function get_suffix_for_seq(seq_depth)
{
	return seq_depth == 0? "" : seq_depth
}

NR==1	{
	print "# Automatically generated from template - EDITS WILL BE LOST"
	print ""
	print "# Generated by module.awk "
	print ""
	print "from pydicom.sequence import Sequence"
	print "from pydicom.dataset import Dataset"
	print "from rightdicom.dcmvfy.strval_h import *"
	print "from rightdicom.dcmvfy.condn_h import *"
	print "from rightdicom.dcmvfy.binval_h import *"
	print "from rightdicom.dcmvfy.tagval_h import *"
	print "from rightdicom.dcmvfy.module_cc import *"
	print "from rightdicom.dcmvfy.attrverify_cc import *"
	print "from pydicom.datadict import *"
	print "from rightdicom.dcmvfy.mesgtext_cc import *"
	print "import rightdicom.dcmvfy.data_elementx"

	
	module=""
	macroormodule=""
}

/^[ 	]*Module=/ || /^[ 	]*DefineMacro=/ {

	module=""
	macroormodule=""
	if (match($0,"Module=\"[^\"]*\"")) {
		macroormodule="Module"
		module=substr($0,RSTART+length("Module=\""), 
			RLENGTH-length("Module=\"")-1);
		}
	else if (match($0,"DefineMacro=\"[^\"]*\"")) {
		macroormodule="Macro"	# not DefineMacro
		module=substr($0,RSTART+length("DefineMacro=\""), 
			RLENGTH-length("DefineMacro=\"")-1);
		}

	print "def " macroormodule "_" module "_verify(ds:Dataset , parent_ds:Dataset, root_ds:Dataset, verbose:bool, log:list, fix_trivials:bool)->bool:"

		print "\tpartial_success = True"
		print "\tglobal_success = True"
		print ""
		print "\tif verbose:"
		print "\t\tlog.append( MMsgDC(\"Verifying\") + MMsgDC(\"" macroormodule "\") +\""module"\")"
		print ""
	sequencenestingdepth=0;
	seq_depth_counter=0;
}

/^[ 	]*ModuleEnd/ || /^[ 	]*MacroEnd/{

		print "\treturn global_success"

		print ""
	module=""
	if (sequencenestingdepth != 0)
		print "Error - sequence nesting depth invalid ( " sequencenestingdepth ") - missing or extra SequenceEnd at line " FNR >"/dev/tty"

}

/^[ 	]*Sequence=/ {

	donotsetused="F"
	if (match($0,"DoNotSetUsed=\"[^\"]*\""))
		donotsetused="T";

	sequence=""
	if (match($0,"Sequence=\"[^\"]*\""))
		sequence=substr($0,RSTART+length("Sequence=\""), 
			RLENGTH-length("Sequence=\"")-1);

	type=""
	if (match($0,"Type=\"[^\"]*\""))
		type=substr($0,RSTART+length("Type=\""), 
			RLENGTH-length("Type=\"")-1);

	vm=""
	match($0,"VM=\"[^\"]*\"");
	vm=substr($0,RSTART+length("VM=\""),RLENGTH-length("VM=\"")-1);
	if (vm == "") {
		print "Warning - missing number of sequence items (VM) at line " FNR >"/dev/tty"
		vm="n";	# supresses checking
	}
	vmmin=vmmax=vm;
	if (vm == "n") {
		vmmin=0;
		vmmax="0xFFFFFFFF";
	}
	if (match(vm,"-")) {
		match(vm,"[0-9]*-");
		vmmin=substr(vm,RSTART,RLENGTH-1);
		match(vm,"-[0-9n]");
		vmmax=substr(vm,RSTART+1,RLENGTH-1);
		if (vmmax == "n") vmmax="0xFFFFFFFF";
	}

	condition=""
	if (match($0,"Condition=\"[^\"]*\""))
		condition=substr($0,RSTART+length("Condition=\""), 
			RLENGTH-length("Condition=\"")-1);

	noconditionpresent="no"
	if (match($0,"NoCondition=\"[^\"]*\""))
		noconditionpresent="yes";

	mbpo="false"
	if (match($0,"[Mm]bpo=\"[^\"]*\""))
		mbpo=substr($0,RSTART+length("mbpo=\""), 
			RLENGTH-length("mbpo=\"")-1);
	
	if (length(sequence) > 0) {
		#if (sequencenestingdepth != 0)
			#print "\tAttribute *" sequence " = (*list)[TagFromName(" sequence ")];"



			
			suffix = get_suffix_for_seq(seq_depth_counter)
			if (donotsetused == "F")
			{ 
				indentcode(sequencenestingdepth)
				print("\tif \"" sequence "\" in ds"suffix":")
				indentcode(sequencenestingdepth)
				print("\t\tds"suffix"[\""sequence"\"].used_in_verification = True")
			}

			indentcode(sequencenestingdepth)
			printf("\tpartial_success = ")
			if (length(type) > 0) {
				print "verifyType" type "(ds"suffix", "
			}
			else {
				print "verifyRequired(ds"suffix", "
			}
			

			indentcode(sequencenestingdepth)
			print "\t\t\t\""module "\", "
			indentcode(sequencenestingdepth)
			print "\t\t\t\"" sequence "\", "
			indentcode(sequencenestingdepth)
			print "\t\t\tverbose, log, fix_trivials, "
			indentcode(sequencenestingdepth)
			if (type == "1C" || type == "2C" || type == "3C") {
				if (length(condition) > 0) {
					print "\t\t\tCondition_" condition ", "
				}
				else {
					print "\t\t\t0, "
					if (noconditionpresent == "no") {
						print "Warning - missing Condition at line " FNR >"/dev/tty"
					}
				}
				if (type == "1C" || type == "2C") {		# mbpo never applies to Type 3C
					indentcode(sequencenestingdepth)
					print "\t\t\t"(mbpo=="true"? "True":"False")", "
				}
				indentcode(sequencenestingdepth)
				print "\t\t\tparent_ds"suffix", root_ds, "
			}
			else {
				if (length(condition) > 0) {
					print "Error - unwanted Condition at line " FNR >"/dev/tty"
				}
			}
			indentcode(sequencenestingdepth)
			print "\t\t\t" vmmin ", "vmmax ")"
			indentcode(sequencenestingdepth)
			print "\tglobal_success = global_success and partial_success "

			indentcode(sequencenestingdepth)
			print "\tif verbose:"
			indentcode(sequencenestingdepth)
			print "\t\tlog.append( \"" module " success after verifying " sequence "\" + (\"success\" if partial_success else \"failure\")) ";
		}

		# create new state for subsequent stuff enclosed in sequence ...
		seq_depth_counter++
		suffix = get_suffix_for_seq(seq_depth_counter)
		indentcode(sequencenestingdepth)
		print "\tif \""sequence"\" in ds"get_suffix_for_seq(seq_depth_counter-1)":"
		indentcode(sequencenestingdepth)
		print "\t\t"sequence"_data = ds"get_suffix_for_seq(seq_depth_counter-1)"."sequence
		indentcode(sequencenestingdepth)
		print "\t\tif type("sequence"_data) == Sequence:"
		indentcode(sequencenestingdepth)
		print "\t\t\tfor i"suffix" in range(0, len("sequence"_data)):"
		indentcode(sequencenestingdepth)
		print "\t\t\t\tif verbose:"
		indentcode(sequencenestingdepth)
		print "\t\t\t\t\tlog.append( \" " sequence " item [{}]\".format(i"suffix"+1))";
		indentcode(sequencenestingdepth)
		print "\t\t\t\tparent_ds"suffix" = ds"get_suffix_for_seq(seq_depth_counter-1)""		
		indentcode(sequencenestingdepth)
		print "\t\t\t\tds"suffix" = "sequence"_data[i"suffix"]"
		sequencenestingdepth+=3

		
	
}

/^[ 	]*SequenceEnd/ {

	sequencenestingdepth-=3
	seq_depth_counter--
	

	# take down nesting for stuff enclosed in sequence ...

	#indentcode(sequencenestingdepth)
	#print "\t\t\t}"
	#indentcode(sequencenestingdepth)
	#print "\t\t}"
	#indentcode(sequencenestingdepth)
	#print "\t}"
}

/^[ 	]*(Name|Verify)=/ {

	donotsetused="F"
	if (match($0,"DoNotSetUsed=\"[^\"]*\""))
		donotsetused="T";

	name=""
	if (match($0,"Name=\"[^\"]*\""))
		name=substr($0,RSTART+length("Name=\""), 
			RLENGTH-length("Name=\"")-1);

	verify=""
	if (match($0,"Verify=\"[^\"]*\""))
		verify=substr($0,RSTART+length("Verify=\""), 
			RLENGTH-length("Verify=\"")-1);

	type=""
	if (match($0,"Type=\"[^\"]*\""))
		type=substr($0,RSTART+length("Type=\""), 
			RLENGTH-length("Type=\"")-1);

	stringdefinedterms=""
	if (match($0,"StringDefinedTerms=\"[^\"]*\""))
		stringdefinedterms=substr($0,RSTART+length("StringDefinedTerms=\""), 
			RLENGTH-length("StringDefinedTerms=\"")-1);

	stringenumvalues=""
	if (match($0,"StringEnumValues=\"[^\"]*\""))
		stringenumvalues=substr($0,RSTART+length("StringEnumValues=\""), 
			RLENGTH-length("StringEnumValues=\"")-1);

	binaryenumvalues=""
	if (match($0,"BinaryEnumValues=\"[^\"]*\""))
		binaryenumvalues=substr($0,RSTART+length("BinaryEnumValues=\""), 
			RLENGTH-length("BinaryEnumValues=\"")-1);

	tagenumvalues=""
	if (match($0,"TagEnumValues=\"[^\"]*\""))
		tagenumvalues=substr($0,RSTART+length("TagEnumValues=\""), 
			RLENGTH-length("TagEnumValues=\"")-1);

	binarybitmap=""
	if (match($0,"BinaryBitMap=\"[^\"]*\""))
		binarybitmap=substr($0,RSTART+length("BinaryBitMap=\""), 
			RLENGTH-length("BinaryBitMap=\"")-1);

	match($0,"VM=\"[^\"]*\"");
	vm=substr($0,RSTART+length("VM=\""),RLENGTH-length("VM=\"")-1);
	if (vm == "") vm=0;
	vmmin=vmmax=vm;
	if (vm == "n") {
		vmmin=1;
		vmmax="0xFFFFFFFF";
	}
	if (match(vm,"-")) {
		match(vm,"[0-9]*-");
		vmmin=substr(vm,RSTART,RLENGTH-1);
		match(vm,"-[0-9n]");
		vmmax=substr(vm,RSTART+1,RLENGTH-1);
		if (vmmax == "n") vmmax="0xFFFFFFFF";
	}

	selector=""
	if (match($0,"ValueSelector=\"[^\"]*\""))
		selector=substr($0,RSTART+length("ValueSelector=\""), 
			RLENGTH-length("ValueSelector=\"")-1);

	if (length(selector) == 0) {
		selector="-1"		# default is wildcard not 1st value !
	}
	else if (selector == "*") {
		selector="-1"		# wildcard
	}

	condition=""
	if (match($0,"Condition=\"[^\"]*\""))
		condition=substr($0,RSTART+length("Condition=\""), 
			RLENGTH-length("Condition=\"")-1);

	noconditionpresent="no"
	if (match($0,"NoCondition=\"[^\"]*\""))
		noconditionpresent="yes";

	mbpo="false"
	if (match($0,"[Mm]bpo=\"[^\"]*\""))
		mbpo=substr($0,RSTART+length("mbpo=\""), 
			RLENGTH-length("mbpo=\"")-1);

	notzero="no"
	if (match($0,"NotZeroWarning=\"[^\"]*\"")) {
		notzero="warning";
	}
	else if (match($0,"NotZeroError=\"[^\"]*\"")) {
		notzero="error";
	}
	
	message=""
	messageConditionModifier=""
	messageErrorOrWarning=""
	if (match($0,"ThenErrorMessage=\"[^\"]*\"")) {
		messageErrorOrWarning="E"
		message=substr($0,RSTART+length("ThenErrorMessage=\""), 
			RLENGTH-length("ThenErrorMessage=\"")-1);
	}
	if (match($0,"ThenWarningMessage=\"[^\"]*\"")) {
		messageErrorOrWarning="W"
		message=substr($0,RSTART+length("ThenWarningMessage=\""), 
			RLENGTH-length("ThenWarningMessage=\"")-1);
	}
	if (match($0,"ThenMessage=\"[^\"]*\"")) {
		messageErrorOrWarning="M"
		message=substr($0,RSTART+length("ThenMessage=\""), 
			RLENGTH-length("ThenMessage=\"")-1);
	}
	
	if (match($0,"ElseErrorMessage=\"[^\"]*\"")) {
		messageErrorOrWarning="E"
		messageConditionModifier=" not "
		message=substr($0,RSTART+length("ElseErrorMessage=\""), 
			RLENGTH-length("ElseErrorMessage=\"")-1);
	}
	if (match($0,"ElseWarningMessage=\"[^\"]*\"")) {
		messageErrorOrWarning="W"
		messageConditionModifier=" not "
		message=substr($0,RSTART+length("ElseWarningMessage=\""), 
			RLENGTH-length("ElseWarningMessage=\"")-1);
	}
	if (match($0,"ElseMessage=\"[^\"]*\"")) {
		messageErrorOrWarning="M"
		messageConditionModifier=" not "
		message=substr($0,RSTART+length("ElseMessage=\""), 
			RLENGTH-length("ElseMessage=\"")-1);
	}

	showValueWithMessage="false"
	if (match($0,"ShowValueWithMessage=\"[^\"]*\""))
		showValueWithMessage=substr($0,RSTART+length("ShowValueWithMessage=\""), 
			RLENGTH-length("ShowValueWithMessage=\"")-1);
	
	if (length(name) > 0) {
#		if (sequencenestingdepth != 0) {
			
#			indentcode(sequencenestingdepth)
#			print "\tAttribute *" name " = (*list)[TagFromName(" name ")];"
#		}

			#if (length(name) > 0) {
			#	indentcode(sequencenestingdepth)
#			if (donotsetused == "F") 
#				printf("\tif (" name ") " name "->setUsed();\n") 
			if (donotsetused == "F")
			{ 
				indentcode(sequencenestingdepth)
				print("\tif \"" name "\" in ds"get_suffix_for_seq(seq_depth_counter)":")
				indentcode(sequencenestingdepth)
				print("\t\tds"get_suffix_for_seq(seq_depth_counter)"[\""name"\"].used_in_verification = True")
			}
			indentcode(sequencenestingdepth)
			printf("\tpartial_success =  ");
			if (length(type) > 0) 
				print "\t\tverifyType" type"(ds"get_suffix_for_seq(seq_depth_counter)", "
			else 
				print "\t\tverifyRequired(ds"get_suffix_for_seq(seq_depth_counter)" , "
			indentcode(sequencenestingdepth)
			print "\t\t\t\"" module "\", \"" name "\", "
			indentcode(sequencenestingdepth)
			print "\t\t\tverbose, log, fix_trivials, "
			indentcode(sequencenestingdepth)
			if (type == "1C" || type == "2C" || type == "3C") {
				if (length(condition) > 0)
					print "\t\t\tCondition_" condition ", "
				else {
					print "\t\t\t0, "
					if (noconditionpresent == "no") 
						print "Warning - missing Condition at line " FNR >"/dev/tty"
				}
				if (type == "1C" || type == "2C") {		# mbpo never applies to Type 3C
					indentcode(sequencenestingdepth)
					print "\t\t\t" (mbpo=="true"? "True":"False") ", "
				}
				indentcode(sequencenestingdepth)
				print "\t\t\tparent_ds"get_suffix_for_seq(seq_depth_counter)", root_ds, "
			}
			else {
				if (length(condition) > 0) 
					print "Error - unwanted Condition at line " FNR >"/dev/tty"
			}
			indentcode(sequencenestingdepth)
			print "\t\t\t" vmmin ", "vmmax ")"
			indentcode(sequencenestingdepth)
			print "\tglobal_success = global_success and partial_success "
			indentcode(sequencenestingdepth)
			print "\tif verbose:"
			indentcode(sequencenestingdepth)
			print "\t\tlog.append( \" " module " success after verifying " name " --> \"+(\"success\" if partial_success else \"failure\"))";
	}

	if ((length(name) > 0 || length(verify) > 0) ) {
		if (length(name) == 0 && length(verify) > 0) name=verify;
		if (length(verify) > 0 && vm != "0") {		# check that VM was explicitly specified and do NOT repeat VM check for other than verify case
			print ""
			if (length(condition) > 0) {
				indentcode(sequencenestingdepth)
				print "\tif not Condition_" condition "(ds"get_suffix_for_seq(seq_depth_counter)", parent_ds"get_suffix_for_seq(seq_depth_counter)", root_ds):"
				sequencenestingdepth++
			}
			indentcode(sequencenestingdepth)
			print "\tif \""name"\" not in ds"get_suffix_for_seq(seq_depth_counter)": "
			indentcode(sequencenestingdepth)
			print "\t\tpartial_success = False "
			indentcode(sequencenestingdepth)
			print "\telse: "
			indentcode(sequencenestingdepth)
			print "\t\tpartial_success = verifyVM(ds"get_suffix_for_seq(seq_depth_counter)"[\"name\"], "
			indentcode(sequencenestingdepth)
			print "\t\t\t\"" module "\", \"" name "\", log, fix_trivials, "vmmin ", "vmmax ", \"" condition "\")"	# use condition as source
			if (length(condition) > 0) 
				--sequencenestingdepth
		}
		if (length(stringdefinedterms) > 0) {
			print ""
			if (length(condition) > 0) {
				indentcode(sequencenestingdepth)
				print "\tif Condition_" condition "(ds"get_suffix_for_seq(seq_depth_counter)", parent_ds"get_suffix_for_seq(seq_depth_counter)", root_ds):"
				sequencenestingdepth++
			}
			indentcode(sequencenestingdepth)
			print "\tif \""name"\" not in ds"get_suffix_for_seq(seq_depth_counter)": "
			indentcode(sequencenestingdepth)
			print "\t\tpartial_success = False "
			indentcode(sequencenestingdepth)
			print "\telse: "
			indentcode(sequencenestingdepth)
			print "\t\tpartial_success = verifyDefinedTerms(ds"get_suffix_for_seq(seq_depth_counter)"[\""name"\"], "
			indentcode(sequencenestingdepth)
			print "\t\t\tStringValueTable_" stringdefinedterms ", "
			indentcode(sequencenestingdepth)
			print "\t\t\tverbose, log, "selector ")"
			indentcode(sequencenestingdepth)
			print "\tglobal_success = global_success and partial_success "
			if (length(condition) > 0) 
				--sequencenestingdepth
			indentcode(sequencenestingdepth)
			print "\tif verbose:"
			indentcode(sequencenestingdepth)
			print "\t\tlog.append( \" " module " success after verifying string defined terms " name " --> \"+(\"success\" if partial_success else \"failure\"))";
		}
		if (length(stringenumvalues) > 0) {
			print ""
			if (length(condition) > 0) {
				indentcode(sequencenestingdepth)
				print "\tif Condition_" condition "(ds"get_suffix_for_seq(seq_depth_counter)", parent_ds"get_suffix_for_seq(seq_depth_counter)", root_ds):"
				sequencenestingdepth++
			}
			indentcode(sequencenestingdepth)
			print "\tif \""name"\" not in ds"get_suffix_for_seq(seq_depth_counter)": "
			indentcode(sequencenestingdepth)
			print "\t\tpartial_success = False "
			indentcode(sequencenestingdepth)
			print "\telse:" 
			indentcode(sequencenestingdepth)
			print "\t\tpartial_success = verifyEnumValues(ds"get_suffix_for_seq(seq_depth_counter)"[\""name"\"], "
			indentcode(sequencenestingdepth)
			print "\t\t\tStringValueTable_" stringenumvalues ", "
			indentcode(sequencenestingdepth)
			print "\t\t\tverbose, log, "selector ")"
			indentcode(sequencenestingdepth)
			print "\tglobal_success = global_success and partial_success "
			if (length(condition) > 0) 
				--sequencenestingdepth
			indentcode(sequencenestingdepth)
			print "\tif verbose:"
			indentcode(sequencenestingdepth)
			print "\t\tlog.append( \" " module " success after verifying string enumerated values " name " --> \"+(\"success\" if partial_success else \"failure\"))";
		}
		if (length(binaryenumvalues) > 0) {
			print ""
			
			if (length(condition) > 0) {
				indentcode(sequencenestingdepth)
				print "\tif Condition_" condition "(ds"get_suffix_for_seq(seq_depth_counter)", parent_ds"get_suffix_for_seq(seq_depth_counter)", root_ds):"
				sequencenestingdepth++
				
			}
			indentcode(sequencenestingdepth)
			print "\tif \""name"\" not in ds"get_suffix_for_seq(seq_depth_counter)": "
			indentcode(sequencenestingdepth)
			print "\t\tpartial_success = False "
			indentcode(sequencenestingdepth)
			print "\telse:" 
			indentcode(sequencenestingdepth)
			print "\t\tpartial_success = verifyEnumValues_uint16(ds"get_suffix_for_seq(seq_depth_counter)"[\""name"\"], "
			indentcode(sequencenestingdepth)
			print "\t\t\tBinaryValueDescription_" binaryenumvalues ", "
			indentcode(sequencenestingdepth)
			print "\t\t\tverbose, log, "selector ")"
			indentcode(sequencenestingdepth)
			print "\tglobal_success = global_success and partial_success "
			if (length(condition) > 0) 
				--sequencenestingdepth
			indentcode(sequencenestingdepth)
			print "\tif verbose:"
			indentcode(sequencenestingdepth)
			print "\t\tlog.append( \" " module " success after verifying binary enumerated values " name " --> \"+(\"success\" if partial_success else \"failure\"))";
		}
		if (length(tagenumvalues) > 0) {
			print ""
			if (length(condition) > 0) {
				indentcode(sequencenestingdepth)
				print "\tif Condition_" condition "(ds"get_suffix_for_seq(seq_depth_counter)", parent_ds"get_suffix_for_seq(seq_depth_counter)", root_ds):"
				sequencenestingdepth++
			}
			indentcode(sequencenestingdepth)
			print "\tif \""name"\" not in ds"get_suffix_for_seq(seq_depth_counter)": "
			indentcode(sequencenestingdepth)
			print "\t\tpartial_success = False "
			indentcode(sequencenestingdepth)
			print "\telse:" 
			indentcode(sequencenestingdepth)
			print "\t\tpartial_success = verifyEnumValues_tag(ds"get_suffix_for_seq(seq_depth_counter)"[\""name"\"], "
			indentcode(sequencenestingdepth)
			print "\t\t\tTagValueDescription_" tagenumvalues ", "
			indentcode(sequencenestingdepth)
			print "\t\t\tverbose, log, "selector ")"
			indentcode(sequencenestingdepth)
			print "\tglobal_success = global_success and partial_success "
			if (length(condition) > 0) 
				--sequencenestingdepth
			indentcode(sequencenestingdepth)
			print "\tif verbose:"
			indentcode(sequencenestingdepth)
			print "\t\tlog.append( \" " module " success after verifying tag enumerated values " name " --> \"+(\"success\" if partial_success else \"failure\"))";
		}
		if (length(binarybitmap) > 0) {
			print ""
			if (length(condition) > 0) {
				indentcode(sequencenestingdepth)
				print "\tif Condition_" condition "(ds"get_suffix_for_seq(seq_depth_counter)", parent_ds"get_suffix_for_seq(seq_depth_counter)", root_ds):"
				sequencenestingdepth++
			}
			indentcode(sequencenestingdepth)
			print "\tif \""name"\" not in ds"get_suffix_for_seq(seq_depth_counter)": "
			indentcode(sequencenestingdepth)
			print "\t\tpartial_success = False "
			indentcode(sequencenestingdepth)
			print "\telse:" 
			indentcode(sequencenestingdepth)
			print "\t\tpartial_success = verifyEnumValues_uint16(ds"get_suffix_for_seq(seq_depth_counter)"[\""name"\"], "
			indentcode(sequencenestingdepth)
			print "\t\t\tBinaryBitMapDescription_" binarybitmap ", "
			indentcode(sequencenestingdepth)
			print "\t\t\tverbose, log, "selector ")"
			indentcode(sequencenestingdepth)
			print "\tglobal_success = global_success and partial_success "
			if (length(condition) > 0) 
				--sequencenestingdepth
			indentcode(sequencenestingdepth)
			print "\tif verbose:"
			indentcode(sequencenestingdepth)
			print "\t\tlog.append( \" " module " success after verifying BitMap enumerated values " name " --> \"+(\"success\" if partial_success else \"failure\"))";
		}
		if (notzero != "no") {
			print ""
			if (length(condition) > 0) {
				indentcode(sequencenestingdepth)
				print "\tif Condition_" condition "(ds"get_suffix_for_seq(seq_depth_counter)", parent_ds"get_suffix_for_seq(seq_depth_counter)", root_ds):"
				sequencenestingdepth++
			}
			indentcode(sequencenestingdepth)
			print "\tif \""name"\" not in ds"get_suffix_for_seq(seq_depth_counter)": "
			indentcode(sequencenestingdepth)
			print "\t\tpartial_success = False "
			indentcode(sequencenestingdepth)
			print "\telse: "
			indentcode(sequencenestingdepth)
			print "\t\tpartial_success = verifyNotZero(ds"get_suffix_for_seq(seq_depth_counter)"[\""name"\"], "
			indentcode(sequencenestingdepth)
			print "\t\t\tverbose, log, "selector ", "(notzero == "warning" ? "True" : "False") ")"
			if (length(condition) > 0) 
				--sequencenestingdepth
		}
		if (length(message) > 0 && length(messageErrorOrWarning) > 0) {
			print ""
			if (length(condition) > 0) {
				indentcode(sequencenestingdepth)
				print "\tif " messageConditionModifier "Condition_" condition "(ds"get_suffix_for_seq(seq_depth_counter)", parent_ds"get_suffix_for_seq(seq_depth_counter)", root_ds):"
				sequencenestingdepth++
			}
			
			indentcode(sequencenestingdepth)
			printf "\t\tlog.append( " messageErrorOrWarning "MsgDC(\"Null\") +\" " message " - attribute <" name ">\""
			if (showValueWithMessage == "true") {
				print "+\\"
				indentcode(sequencenestingdepth)
				print "\t\t\t\" = <{}>\".format( ds." name "))"
			}
			else
				print ")"
			
			if (length(condition) > 0) 
				--sequencenestingdepth
		}
		print ""
	}
	
	}

/^[	 ]*InvokeMacro=/ {

    invokedmacro=""
    if (match($0,"InvokeMacro=\"[^\"]*\""))
        invokedmacro=substr($0,RSTART+length("InvokeMacro=\""), 
            RLENGTH-length("InvokeMacro=\"")-1);

    condition=""
    if (match($0,"Condition=\"[^\"]*\""))
        condition=substr($0,RSTART+length("Condition=\""), 
            RLENGTH-length("Condition=\"")-1);


			if (length(condition) > 0) {
				indentcode(sequencenestingdepth)
				print "\tif Condition_" condition "(ds"get_suffix_for_seq(seq_depth_counter)", parent_ds"get_suffix_for_seq(seq_depth_counter)", root_ds):"
				sequencenestingdepth++

			}
			indentcode(sequencenestingdepth)
			print "\tpartial_success =  Macro_" invokedmacro "_verify(ds"get_suffix_for_seq(seq_depth_counter)", parent_ds"get_suffix_for_seq(seq_depth_counter)", root_ds, verbose, log, fix_trivials)"
			if (length(condition) > 0)
				sequencenestingdepth--
			print ""
			indentcode(sequencenestingdepth)
			print "\tif verbose:"
			indentcode(sequencenestingdepth)
			print "\t\tlog.append( \" " module " success after verifying " invokedmacro "\"+ (\"success\" if partial_success else \"failure\" ))";
    
    }


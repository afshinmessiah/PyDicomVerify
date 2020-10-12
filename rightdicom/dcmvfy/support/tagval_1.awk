#  tagval.awk Copyright (c) 1993-2018, David A. Clunie DBA PixelMed Publishing. All rights reserved.
# create C++ headers from tag values template 

# can set these values on the command line:
#


NR==1	{
	print "# Automatically generated from template - EDITS WILL BE LOST"
	print ""
	print "# Generated by tagval.awk with options " role " " outname
	print ""
	print "from numpy import *"



	mode=""
	}

/^[ 	]*TagValues/ {
	name=""
	if (match($0,"TagValues=\"[^\"]*\""))
		name=substr($0,RSTART+length("TagValues=\""),
			RLENGTH-length("TagValues=\"")-1);

		print "def TagValueDescription_" name "(group:uint16,element:uint16)->str:"
		print "\tost = \"\""
		print "\tvalue=(uint32(group)<<16)|element"
		n = 0
		
	}

/^[ 	]*0x[0-9a-fA-F]*/ {
	n ++
	valueline=$0
	if (!match(valueline,"[0-9][x0-9a-fA-F]*,[0-9][x0-9a-fA-F]*")) {
		print "Line " FNR \
			": error in value line - no group,element code <" \
			valueline ">" >"/dev/tty"
		next
	}
	code=substr(valueline,RSTART,RLENGTH)
	valueline=substr(valueline,RSTART+RLENGTH)

	group=""
	if (match(code,"[0-9][x0-9a-fA-F]*,")) {
		group=substr(code,RSTART,RLENGTH-1)
	}
	element=""
	if (match(code,",[0-9][x0-9a-fA-F]*")) {
		element=substr(code,RSTART+1,RLENGTH-1)
	}

	if (match(valueline,"[ 	]*=[ 	]*")) {
		meaning=substr(valueline,RSTART+RLENGTH)
		if (match(meaning,"[ 	]*,*[ 	]*$")) {
			meaning=substr(meaning,0,RSTART-1)
		}
	}
	else {
		meaning=code
	}

	if (group == "" || element == "") {
		print "Line " FNR \
			": error in value line - can't interpret group,element code <" \
			$0 ">" >"/dev/tty"
	}
	else {
		if(n==1)
			print "\tif value == (uint32("group")<<16)|"element" :" 
		else
			print "\telif value == (uint32("group")<<16)|"element" :"
		
			
			print "\t\tost += \"" meaning "\" "
			print "\t\treturn ost"
	}

	}

/^[ 	]*}/ {
		print "\telse:"
		print "\t\treturn \"\""

		print ""

	mode=""
	}



# MSFS-tools

Various tools that are useful to Microsoft Flight Simulator add-on developers. Or at least to myself when I develop such add-ons.

## template-expand.py

This Python script reads an aircraft model XML file and expands the template calls in it. It is a work in progress. I don't know whether it
will ever be "finished" and complete. But now it is able to process the whole DA62_interior.xml from the SDK samples.
Input events (elements UseInputEvent, Extend, Presets, Preset, and others?) are not handled in any way yet, and it is very unclear
to me how they should be handled, sorry.
But at least this might help a bit in understanding what the real low-level API of this stuff is, that is hidden
under layer upon layer of templates.

Use: `python3 template-expand.py --verbose --include ~/Downloads/ModelBehaviorDefs a.xml`

(That is on macOS or Linux. The Unix command line is my preferred environment. But something similar will work on Windows, too.)

Where the `~/Downloads/ModelBehaviorDefs` is where I have copied the OneStore/fs-base-aircraft-common/ModelBehaviorDefs from MSFS and
fixed the XML syntax errors in it. (The fixes I did are in `ModelBehaviorDefs-fixes.diff`.)

## js-to-loc

a Python script to make maintaining message catalogs easier
    
The script takes one or several message catalogs in a trimmed-down
JSON format without any extra metadata and turns them into a more
complex .loc file that the MSFS packaging process then again will turn
into a set of simpler .locPak files.

It is unclear whether the metadata attributes UUID, LastModifiedBy,
LastModifiedDate, and LocalizationStatus actually are needed for each
string in the message catalog, but better safe than sorry.

The input is in the format:

	{
		"Language": "en-US",
		"Strings": {
			"AIRCRAFT.DESCRIPTION": "This aircraft is extremely cool.",
			"FOO.LABEL_FLUSH_FLUX_CAPACITOR": "Flush the flux capacitor",
			"FOO.LABEL_DROP_ACID": "Inject extra acid into engine"
		}
	}

And the output is then:

	{
	  "LocalisationFile": {
		"Version": 2,
		"UUID": "8052a1b8-13b1-473c-b07b-22683bf847bf",
		"Languages": [
		  "en-US"
		],
		"Strings": {
		  "AIRCRAFT.DESCRIPTION": {
			"UUID": "847ac482-b857-4acd-87f0-39fb61910a5b",
			"LastModifiedBy": "tml",
			"LastModifiedDate": "2022-01-25 00:40:16",
			"LocalizationStatus": "TranslationNeeded",
			"Languages": {
			  "en-US": {
				"Text": "This aircraft is extremely cool.",
				"LocalizationStatus": "TranslationNeeded"
			  }
			}
		  },
		  "FOO.LABEL_FLUSH_FLUX_CAPACITOR": {
			"UUID": "523d1261-9d18-49d6-bbe5-a74f03565bcb",
			"LastModifiedBy": "tml",
			"LastModifiedDate": "2022-01-25 00:40:16",
			"LocalizationStatus": "TranslationNeeded",
			"Languages": {
			  "en-US": {
				"Text": "Flush the flux capacitor",
				"LocalizationStatus": "TranslationNeeded"
			  }
			}
		  },
		  "FOO.LABEL_DROP_ACID": {
			"UUID": "333fc921-882b-4211-ad5c-90ac42b350e4",
			"LastModifiedBy": "tml",
			"LastModifiedDate": "2022-01-25 00:40:16",
			"LocalizationStatus": "TranslationNeeded",
			"Languages": {
			  "en-US": {
				"Text": "Inject extra acid into engine",
				"LocalizationStatus": "TranslationNeeded"
			  }
			}
		  }
		}
	  }
	}

cwlVersion: v1.2
class: CommandLineTool
baseCommand: [bash, wrapper.sh]
stdout: output_log.txt 
requirements:
  ShellCommandRequirement: {}
  InitialWorkDirRequirement:
    listing:
      - entryname: wrapper.sh
        entry: |
          #!/bin/bash
          n=1
          while [ -d "/workingdir/scratch$n" ]; do
            n=`expr $n + 1`
          done
          mkdir -p "/workingdir/scratch$n"
          mkdir -p "/outDir/output$n"
          cp "$(inputs.xmlfile.path)" "/workingdir/scratch$n/$(inputs.xmlfile.basename)"
          python3 /Algorithm/sample_sheetTolibInfo.py /workingdir/scratch$n/$(inputs.xmlfile.basename) /outDir/output$n/fof.txt /outDir/output$n/rof.txt $(inputs.configtype)
          exit_code=$?
          cp output_log.txt /workingdir/scratch$n/output_log.txt
          cp wrapper.sh "/workingdir/scratch$n/wrapper.sh"
          exit $exit_code
        writable: false
inputs:
  xmlfile:
    type: File
  configtype:
    type: string
outputs: []
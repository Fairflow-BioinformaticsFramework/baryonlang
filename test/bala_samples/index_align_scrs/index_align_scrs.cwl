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
          while [ -d "/workDir/scratch$n" ]; do
            n=`expr $n + 1`
          done
          mkdir -p "/workDir/scratch$n"
          mkdir -p "/genome"
          mkdir -p "/scratch"
          bash /home/index_align.sh $(inputs.bamsave)
          exit_code=$?
          cp output_log.txt /workDir/scratch$n/output_log.txt
          cp wrapper.sh "/workDir/scratch$n/wrapper.sh"
          exit $exit_code
        writable: false
inputs:
  bamsave:
    type: string
outputs: []
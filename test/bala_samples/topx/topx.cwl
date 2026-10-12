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
          while [ -d "/workdir/scratch$n" ]; do
            n=`expr $n + 1`
          done
          mkdir -p "/workdir/scratch$n"
          mkdir -p "/data"
          mkdir -p "/workdir/scratch$n/$(inputs.data_origin_name)"
          cp -r "/data/." "/workdir/scratch$n/$(inputs.data_origin_name)/"
          Rscript /bin/top.R $(inputs.matrixname) "$(inputs.format)" "$(inputs.separator)" $(inputs.logged) $(inputs.threshold) $(inputs.type)
          exit_code=$?
          cp output_log.txt /workdir/scratch$n/output_log.txt
          cp wrapper.sh "/workdir/scratch$n/wrapper.sh"
          exit $exit_code
        writable: false
inputs:
  data_origin_name:
    type: string
  matrixname:
    type: string
  format:
    type: string
  threshold:
    type: string
  separator:
    type: string
  logged:
    type: string
  type:
    type: string
outputs: []
#!/usr/bin/env zsh

function _bitratecheck_unescape() {
  emulate -L zsh
  setopt localoptions no_shwordsplit
  local input=$1 output='' char next
  integer i=1
  while (( i <= ${#input} )); do
    char=${input[i]}
    if [[ $char == $'\\' ]] && (( i < ${#input} )); then
      (( i++ ))
      next=${input[i]}
      case $next in
        n) output+=$'\n' ;;
        r) output+=$'\r' ;;
        t) output+=$'\t' ;;
        *) output+=$next ;;
      esac
    else
      output+=$char
    fi
    (( i++ ))
  done
  REPLY=$output
}

function _bitratecheck_help() {
  print -r -- 'Usage: bitratecheck [--scan] [--] FILE...'
  print -r -- '       brc [--scan] [--] FILE...'
  print -r -- ''
  print -r -- 'Show bitrate for each video and audio stream in any ffprobe-readable file.'
  print -r -- 'Rates use decimal kb/s (1000 bits/s). Track ID N is ffprobe'
  print -r -- 'global stream index N, which can differ from a container-native track ID.'
  print -r -- ''
  print -r -- '  --scan  Recalculate average rates from packet sizes and timestamps.'
  print -r -- '  --      End options; useful when file names begin with a dash.'
}

function bitratecheck() {
  emulate -L zsh
  setopt localoptions no_shwordsplit no_ksharrays pipefail
  local -x LC_ALL=C
  local REPLY
  local ffprobe_bin=${BITRATECHECK_FFPROBE:-ffprobe}
  local file absolute line key value field scan=0 failed=0 metadata_output
  local type codec rate title lang source index field_lower
  local -a args
  local -A types codecs rates titles langs sources attached
  integer ended_options=0

  if (( $# == 0 )); then
    _bitratecheck_help
    return 0
  fi
  while (( $# )); do
    if (( ! ended_options )) && [[ $1 == -- ]]; then
      ended_options=1; shift; continue
    elif (( ! ended_options )) && [[ $1 == --help || $1 == -h ]]; then
      _bitratecheck_help; return 0
    elif (( ! ended_options )) && [[ $1 == --scan ]]; then
      scan=1; shift; continue
    elif (( ! ended_options )) && [[ $1 == -* ]]; then
      print -u 2 -r -- "bitratecheck: unknown option: $1"
      return 2
    fi
    args+=("$1"); shift
  done
  if (( ${#args[@]} == 0 )); then
    print -u 2 -r -- 'bitratecheck: provide at least one file.'
    return 2
  fi
  if ! (( $+commands[$ffprobe_bin] )) && [[ ! -x $ffprobe_bin ]]; then
    print -u 2 -r -- "bitratecheck: ffprobe executable not found: $ffprobe_bin"
    return 127
  fi

  for file in "${args[@]}"; do
    if [[ ! -f $file || ! -r $file ]]; then
      print -u 2 -r -- "bitratecheck: not a readable file: $file"
      failed=1; continue
    fi
    absolute=${file:A}
    types=(); codecs=(); rates=(); titles=(); langs=(); sources=(); attached=()
    if ! metadata_output=$("$ffprobe_bin" -v error -show_entries 'stream=index,codec_type,codec_name,bit_rate:stream_disposition=attached_pic:stream_tags' -of flat=s=_ -i "$absolute" </dev/null 2>/dev/null); then
      print -u 2 -r -- "bitratecheck: ffprobe could not read: $file"
      failed=1; continue
    fi
    while IFS= read -r line; do
      [[ $line == streams_stream_* ]] || continue
      key=${line%%=*}; value=${line#*=}
      [[ $key =~ '^streams_stream_([0-9]+)_(.+)$' ]] || continue
      index=$match[1]; field=$match[2]
      field_lower=${(L)field}
      if [[ $field_lower == disposition_attached_pic ]]; then
        attached[$index]=$value
        continue
      fi
      [[ $value == \"*\" ]] || continue
      value=${value[2,-2]}
      case $field in
        codec_type) types[$index]=$value ;;
        codec_name) codecs[$index]=$value ;;
        bit_rate) [[ $value == <-> ]] && (( value > 0 )) && { rates[$index]=$value; sources[$index]=stored; } ;;
        *)
          case $field_lower in
            # The flat writer turns tag-name punctuation into underscores.
            tags_bps|tags_bps_*)
              if [[ -z ${rates[$index]-} && $value == <-> ]] && (( value > 0 )); then
                rates[$index]=$value; sources[$index]=stored
              fi ;;
            tags_title) _bitratecheck_unescape "$value"; titles[$index]=$REPLY ;;
            tags_language) _bitratecheck_unescape "$value"; langs[$index]=$REPLY ;;
          esac ;;
      esac
    done <<< "$metadata_output"
    if (( ${#types[@]} == 0 )); then
      print -u 2 -r -- "bitratecheck: no readable streams found: $file"
      failed=1; continue
    fi
    local -i av_count=0
    for index in ${(k)types}; do
      if [[ ${types[$index]} == (video|audio) ]] && ! { [[ ${types[$index]} == video ]] && [[ ${attached[$index]-0} == 1 ]]; }; then
        (( av_count++ ))
      fi
    done
    if (( av_count == 0 )); then
      print -u 2 -r -- "bitratecheck: no video or audio streams found: $file"
      failed=1; continue
    fi
    local -i need_scan=$scan
    if (( ! need_scan )); then
      for index in ${(k)types}; do
        type=${types[$index]}
        [[ $type == video && ${attached[$index]-0} == 1 ]] && continue
        if [[ $type == (video|audio) && -z ${rates[$index]-} ]]; then need_scan=1; break; fi
      done
    fi
    if (( need_scan )); then
      if (( scan )); then
        for index in ${(k)types}; do
          if [[ ${types[$index]} == (video|audio) ]] && ! { [[ ${types[$index]} == video ]] && [[ ${attached[$index]-0} == 1 ]]; }; then
            unset "rates[$index]" "sources[$index]"
          fi
        done
      fi
      print -u 2 -r -- "bitratecheck: scanning packets: $file"
      local packet_result=''
      packet_result=$("$ffprobe_bin" -v error -show_packets -show_entries packet=stream_index,size,pts_time,dts_time,duration_time -of compact=p=0:nk=0 -i "$absolute" </dev/null 2>/dev/null | awk '
        {
          delete field
          count=split($0, parts, "|")
          for (j=1; j<=count; j++) {
            split(parts[j], pair, "="); field[pair[1]]=pair[2]
          }
          i=field["stream_index"]; size=field["size"]
          if (i !~ /^[0-9]+$/ || size !~ /^[0-9]+$/) next
          bytes[i]+=size
          t=field["pts_time"]; if (t !~ /^-?[0-9]+([.][0-9]+)?$/) t=field["dts_time"]
          d=field["duration_time"]
          if (t ~ /^-?[0-9]+([.][0-9]+)?$/) {
            t+=0; d=(d ~ /^[0-9]+([.][0-9]+)?$/ ? d+0 : 0)
            if (!(i in seen) || t<lo[i]) lo[i]=t
            if (!(i in seen) || t+d>hi[i]) hi[i]=t+d
            seen[i]=1
          }
        }
        END { for (i in bytes) if (seen[i] && hi[i]>lo[i]) printf "%s %0.0f\n", i, bytes[i]*8/(hi[i]-lo[i]) }
      ')
      if (( $? != 0 )); then
        print -u 2 -r -- "bitratecheck: packet scan failed: $file"
        failed=1; continue
      fi
      for line in ${(f)packet_result}; do
        index=${line%% *}; rate=${line#* }
        if [[ $index == <-> && $rate == <-> ]] && (( rate > 0 )); then
          if (( scan )) || [[ -z ${rates[$index]-} ]]; then
            rates[$index]=$rate; sources[$index]=calculated
          fi
        fi
      done
    fi
    print -r -- "$file"
    for index in ${(onk)types}; do
      type=${types[$index]}
      [[ $type == (video|audio) ]] || continue
      [[ $type == video && ${attached[$index]-0} == 1 ]] && continue
      codec=${codecs[$index]:-unknown}
      rate=${rates[$index]:-unknown}
      source=${sources[$index]:-unknown}
      if [[ $rate == <-> ]]; then
        printf -v rate '%.1f kb/s (%s)' "$(( rate / 1000.0 ))" "$source"
      fi
      title=${titles[$index]-}; lang=${langs[$index]-}
      print -r -- "  Track ID $index: $type ($codec) — $rate${title:+ [$title]}${lang:+ [$lang]}"
    done
  done
  return $failed
}

function brc() { bitratecheck "$@" }

# When run directly, use the same implementation and preserve the calling shell.
if [[ ${ZSH_EVAL_CONTEXT:-} == toplevel ]]; then
  bitratecheck "$@"
fi

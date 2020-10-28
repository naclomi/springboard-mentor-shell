#!/bin/bash
#
# tourguide.sh - sync the pwd of the shell to the contents of a file
# author: naomi alterman (yours.truly@nlalterman.com)
# last modified: 10/27/2020
#

usage() {
    echo "usage: $0 WATCHFILE [SHELL]"
    echo "      WATCHFILE   a file whose sole contents is the absolute path the"
    echo "                  current shell should jump to"
    echo "      SHELL       the shell to invoke (default is /bin/bash)"
    echo "Make WATCHFILE empty to stop script"
}

if [[ "$#" -lt 1 || "$#" -gt 2 ]]; then
    usage
    exit 1
fi

SHELL=/bin/bash
WATCH_FILE=$(realpath $1)
set -m

if [[ "$#" -gt 1 ]]; then
SHELL=$2
fi

wait_on_file() {
    inotifywait -q -e modify $1 >/dev/null;
}

shell_killswitch(){
    wait_on_file $WATCH_FILE;
    kill -9 $current_shell_pid;
}

pid_to_jobspec(){
    jobs -l | gawk 'match($0, /\[([0-9]+)\].?\s+'$1'/, group) { print group[1] }'
}

run_loop() {
    while [ -s $WATCH_FILE ]
    do
        new_dir=`cat $WATCH_FILE`;
        pushd "$new_dir" && \
            { $SHELL & export current_shell_pid=$!; } &&
            popd &&
            { shell_killswitch & fg `pid_to_jobspec $current_shell_pid`; }
    done
}

run_loop

# end of line <3

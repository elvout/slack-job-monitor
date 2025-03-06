#

Hacky script to monitor the progress of batch jobs in slack.

## Setup

Add this to your pyproject

`slack-job-monitor @ git+https://github.com/elvout/slack-job-monitor.git"`

Have your slack user id and slack bot token into `SLACK_USER_ID` and `SLACK_BOT_TOKEN` environment vars.

## Usage

Be in the appropriate virtual environment.

Currently only supports commands that take exactly one argument, e.g., a filesystem path or number, etc.

`slack-job-monitor command job_1_arg job_2_arg job_n_arg`

Periodically updates a message like this in slack:
```text
🔵 RUNNING
user@machine:
command
2m elapsed
43/100 (43%) jobs completed (0 failed)
400% cpu (7m user, 1m sys)
Last updated yyyy-mm-ddTHH:MM:SS.ssssss-tz
```

Pings you when the job exits in the shell (but not if it's SIGKILLED or your computer crashes :D)

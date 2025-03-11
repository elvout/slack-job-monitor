#! /usr/bin/env python3

import argparse
import datetime
import enum
import getpass
import itertools
import math
import platform
import subprocess
import time

import human_readable
import human_readable.i18n
import psutil

from slack_job_monitor.slack_wrapper import RateLimiter, SlackClientWrapper


class MonitorStatus(enum.Enum):
    STARTED = "⚪ STARTED"
    RUNNING = "🔵 RUNNING"
    COMPLETED = "🟢 COMPLETED"
    COMPLETED_WITH_ERRORS = "🟠 COMPLETED WITH ERRORS"
    INTERRUPTED = "🔴 INTERRUPTED"
    CRASHED = "🔴 CRASHED"


class ProcessMonitor:
    def __init__(self, command: list[str], args: list[str]) -> None:
        self.command = command
        self.args = args

        self.status = MonitorStatus.STARTED
        self.slack = SlackClientWrapper()
        self.rate_limiter = RateLimiter(4)

        # stats
        self.start = time.time()
        self.completed = 0  # success + failed
        self.failed = 0
        self.user_time = 0.0
        self.system_time = 0.0
        self.real_time = 0.0

        self.update_message("")

    def update_message(self, message: str) -> None:
        message = "\n".join(
            [
                f"{self.status.value}",
                f"{getpass.getuser()}@{platform.node()}:",
                f"`{' '.join(self.command)}`",
                message,
                f"Last updated {datetime.datetime.now().astimezone().isoformat('T')}",
            ]
        )
        self.slack.update_post(message)

    def duration(self, t: float) -> str:
        return (
            human_readable.precise_delta(
                int(t), minimum_unit="minutes", formatting=".0f"
            )
            .replace(" and", ",")
            .replace(", ", "")
        )

    def get_stats_str(self) -> str:
        completed_pct = self.completed / len(self.args) * 100
        cpu_pct = (self.user_time + self.system_time) / (self.real_time) * 100
        return "\n".join(
            [
                f"{self.duration(self.real_time)} elapsed",
                f"{self.completed}/{len(self.args)} ({int(completed_pct)}%) jobs completed ({self.failed} failed)",
                f"{cpu_pct:.0f}% cpu ({self.duration(self.user_time)} user, {self.duration(self.system_time)} sys)",
            ]
        )

    def run_jobs(self) -> None:
        self.status = MonitorStatus.RUNNING

        for arg in self.args:
            try:
                job_start = time.time()

                # Continuously update a dictionary because we can't take statistics of
                # the process once it's terminated.
                proc_stats: dict[psutil.Process, psutil._common.pcputimes] = {}

                proc = subprocess.Popen(self.command + [arg])

                p = psutil.Process(proc.pid)
                while proc.poll() is None:
                    for pc in itertools.chain((p,), p.children(recursive=True)):
                        try:
                            proc_stats[pc] = pc.cpu_times()
                        except psutil.Error:
                            # Process usually does not exist anymore, so we can't get
                            # its stats.
                            pass

                    time.sleep(math.log10(time.time() - job_start + 1))

                proc.wait()
                self.completed += 1
                self.failed += proc.returncode != 0

                self.user_time += sum(s.user for s in proc_stats.values())
                self.system_time += sum(s.system for s in proc_stats.values())
                self.real_time = time.time() - self.start

                if self.rate_limiter():
                    self.update_message(self.get_stats_str())
            except KeyboardInterrupt:
                proc.terminate()
                self.status = MonitorStatus.INTERRUPTED
                break

        self.real_time = time.time() - self.start
        if self.completed == len(self.args):
            if self.failed == 0:
                self.status = MonitorStatus.COMPLETED
            else:
                self.status = MonitorStatus.COMPLETED_WITH_ERRORS
        self.update_message(self.get_stats_str())


def parse_args() -> tuple[list[str], list[str]]:
    """
    returns:
        * command tokens
        * list of command args (single token only supported atm)
    """
    parser = argparse.ArgumentParser("slack-notify")
    parser.add_argument("command", type=str)
    parser.add_argument("arguments", nargs="*")
    # parser.add_argument("-n", type=int, default=-1, required=False)

    args = parser.parse_args()

    command = args.command.split()
    arguments = args.arguments

    # if args.n != -1: ...

    return command, arguments


def main() -> None:
    human_readable.i18n.activate("en_ABBR")

    command, args = parse_args()
    monitor = ProcessMonitor(command, args)
    try:
        monitor.run_jobs()
    except:
        monitor.status = MonitorStatus.CRASHED
        monitor.update_message(monitor.get_stats_str())

    monitor.slack.ping_user()


if __name__ == "__main__":
    main()

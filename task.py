import sh
import sys
import argparse
from pathlib import Path
from datetime import date, timedelta, datetime


def check_pick(reponame: str, fromdate: str, todate: str) -> list[str]:
    repopath = "{0}.git/".format(reponame)
    result: list[str] = []
    needupdate = True
    if not Path("{0}.git/".format(reponame)).exists():
        remoteurl = "https://github.com/qt/{0}".format(reponame)
        depth = 200
        print("Shadow cloning {0} from {1}, depth={2}...".format(reponame, remoteurl, depth))
        sh.git.clone(remoteurl, bare=True, depth=100, _out=sys.stdout, _err=sys.stderr)
        needupdate = False
        print("Done.")

    git = sh.git.bake('-C', repopath, _tty_out=False)
    if needupdate:
        git.fetch(prune=True)
    rangelog = git.log(after=fromdate, before=todate, pretty='format:%H')
    commithashs: list[str] = rangelog.stdout.decode("utf-8").split('\n')

    while("" in commithashs): # if no commit in given date range, it can be an empty string
        commithashs.remove("")

    for commithash in commithashs:
        trailersexec = git(git.show("-s", commithash, format='%b'), "interpret-trailers", "--parse")
        trailers = trailersexec.stdout.decode("utf-8").split('\n')
        for trailer in trailers:
            if trailer.startswith("Pick-to:") and "5.15" in trailer:
                result.append(commithash)
    print("{0}: {1}/{2} commit(s) need to be cherry-picked".format(reponame, len(result), len(commithashs)))
    return result


def query_date(args) -> [str, str]:
    yesterday = date.today() - timedelta(days = 1)
    from_date = yesterday if not args.in_date else datetime.strptime(args.in_date, '%Y-%m-%d')
    to_date = from_date + timedelta(days = 1)
    return [from_date.strftime('%Y-%m-%d'), to_date.strftime('%Y-%m-%d')]


def main():
    parser = argparse.ArgumentParser(
                    prog = 'Qt patch backport helper',
                    description = 'Check commits that might need to backport')
    parser.add_argument('-d', '--dry-run',
                        action='store_true',
                        help='turn on dry-run for debugging')
    parser.add_argument('-i', '--in-date',
                        action='store',
                        help='The date we would like to check',
                        required=False)
    [args, _] = parser.parse_known_args()

    [fromdatestr, todatestr] = query_date(args)

    results: Dict[str, list[str]] = {}

    results["qtbase"] = check_pick("qtbase", fromdatestr, todatestr)
    results["qtsvg"] = check_pick("qtsvg", fromdatestr, todatestr)
    results["qtimageformats"] = check_pick("qtimageformats", fromdatestr, todatestr)

    print("-------- RESULT --------")
    print("Commits in {0}:".format(fromdatestr))
    for reponame, commits in results.items():
        for commithash in commits:
            issue_title = "{0}: commit {1} may need to apply to 5.15 patchset".format(reponame, commithash[:7])
            issue_body = "- Date: {2}\n- Commit: https://github.com/qt/{0}/commit/{1}".format(reponame, commithash, fromdatestr)
            print(issue_title)
            if not args.dry_run:
                sh.gh.issue.create(repo="peeweep-test/dtkcommon", title=issue_title, body=issue_body)


if __name__ == "__main__":
    main()

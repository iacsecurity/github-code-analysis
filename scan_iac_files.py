import logging
import re
import sqlite3 as sl
import time
import datetime
import requests

from github import Github, GithubException
from github.ContentFile import ContentFile

gh_api_token = "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"

re_cfn = re.compile("Resources\:.*AWS", re.DOTALL)
re_helm = re.compile("(namespace: kube-system|name: pod-exec|kind: ClusterRole|apiVersion: .*.k8s.io|apiVersion: v1)")
re_pulumi = re.compile("(P|p)ulumi")

logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)

def determine_iac_type(filename, content):
    if filename.endswith(".tf"):
        return "tf"
    elif (re_cfn.search(content)):
        return "cfn"
    elif (re_helm.search(content)):
        return "helm"
    elif filename.endswith(".py") and re_pulumi.search(content):
        return "pulumi"
    return None

def check_and_wait_for_limits(g):
    search_ratelimit = g.get_rate_limit().search
    if search_ratelimit.remaining == 0:
        seconds_to_sleep = (search_ratelimit.reset - datetime.datetime.utcnow()).total_seconds() + 5 # In case of clock sync issues
        logging.warning (f"Hit search rate limit, sleeping {seconds_to_sleep} seconds...")
        time.sleep(seconds_to_sleep)

    core_ratelimit = g.get_rate_limit().core
    if core_ratelimit.remaining == 0:
        seconds_to_sleep = (core_ratelimit.reset - datetime.datetime.utcnow()).total_seconds() + 5 # In case of clock sync issues
        logging.warning (f"Hit core rate limit, sleeping {seconds_to_sleep} seconds...")
        time.sleep(seconds_to_sleep)


def fetch_iac():
    g = Github(gh_api_token)

    con = sl.connect('gh-file-iac-classification.db')
    # with con:
        # con.execute("""
        #     CREATE TABLE FILE (
        #         url TEXT NOT NULL PRIMARY KEY,
        #         git_url TEXT,
        #         html_url TEXT,
        #         repository_giturl TEXT,
        #         iac TEXT
        #     );
        # """)
        # con.execute("""
        #     CREATE TABLE ORG (
        #         login TEXT NOT NULL PRIMARY KEY
        #     );
        # """)
    
    check_and_wait_for_limits(g)
    for org in g.get_organizations():

        seen_org_before = False
        with con:
            sqlcmd_find_org = """
                select * from ORG where login =?;
                """
            seen_org_before = con.execute(sqlcmd_find_org, (org.login,)).fetchone()

        if seen_org_before:
            logging.info(f"Skipping org: {org.login}")
            continue
        else:
            logging.info(f"Searching org: {org.login}")

        search_org_code(g, con, org, f"Resources in:file language:yaml org:{org.login}") # CFN
        search_org_code(g, con, org, f"apiVersion in:file language:yaml org:{org.login}") # Helm
        search_org_code(g, con, org, f"resource in:file language:hcl org:{org.login}") # HCL
        search_org_code(g, con, org, f"pulumi in:file language:python org:{org.login}") # Pulumi

        check_and_wait_for_limits(g)

        with con:
            sqlcmd_insert_org_info = """
                INSERT INTO ORG (login) values(?)
                    ON CONFLICT(login) DO NOTHING;
            """
            con.execute(sqlcmd_insert_org_info, (org.login,))
            con.commit()

def search_org_code(g, con, org, query):
    code_search = g.search_code(query)
    code_search_iterator = None
    files_reviewed = 0
        
    try:
        while files_reviewed < code_search.totalCount:
            file = None
            while not file:
                try:
                    if not code_search_iterator:
                            # Need to initilize the iterator every once in a while because every
                            # page in the results returns its own set of elements
                        logging.info("Getting new code search iterator")
                        code_search_iterator = iter(code_search)

                    file = next(code_search_iterator)
                except GithubException as e:
                    logging.exception("Hit Github Exception")
                    if e.headers.get("Retry-After", None):
                        logging.info("Sleeping as requested.")
                        time.sleep(int(e.headers["Retry-After"]))
                    else:
                        logging.info("Sleeping a bit (no specific time specified GH).")
                        time.sleep(60)


                except StopIteration:
                        # Need a the next page
                    code_search_iterator = iter(code_search)
            try:
                files_reviewed += 1
                iac_type = determine_iac_type(file.html_url, file.decoded_content.decode('utf-8'))
                if iac_type:
                    logging.info(f"#{files_reviewed}: {file.html_url} is {iac_type}")
                else:
                    logging.info(f"#{files_reviewed}: Failed to determine IaC type for {file.html_url}")

                with con:
                    sqlcmd_insert_file_iac_info = """
                            INSERT INTO FILE (url, git_url, html_url, repository_giturl, iac) values(?, ?, ?, ?, ?)
                                ON CONFLICT(url) DO UPDATE SET iac=excluded.iac;
                        """
                    con.execute(sqlcmd_insert_file_iac_info, (file.url, file.git_url, file.html_url, file.repository.git_url, iac_type))
                    con.commit()
            except Exception:
                logging.exception(f"Issue handling {file.url}")

            check_and_wait_for_limits(g)
    except GithubException as e:
        logging.debug("Generic GithubException")
    except requests.exceptions.ReadTimeout:
        logging.error("ReadTimeout, continuing to the next one")
    except requests.exceptions.ConnectionError:
        logging.error("ConnectionError, continuing to the next one")


if __name__ == '__main__':
    fetch_iac()
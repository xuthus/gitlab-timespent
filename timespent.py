import os
from multiprocessing.dummy import Pool as ThreadPool

import requests
import xlsxwriter
from pyslurpers import JsonSlurper
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class TicketInfo:
    def __init__(self, number: int, project_id: int, dates: set):
        self.dates = dates
        self.project_id = project_id
        self.number = number


def dateToInt(d: str):
    date = d[:10].split("-")
    return int(date[0]) * 10000 + int(date[1]) * 100 + int(date[2])


def parseTimeSpent(note: str, sinceDateInt: int, untilDateInt: int):
    # added 3h of time spent at 2019-06-10
    parts = note.split(" ")
    at_index = parts.index("at")
    of_index = parts.index("of")
    extractedDateInt = dateToInt(parts[at_index + 1])
    if extractedDateInt >= sinceDateInt and extractedDateInt <= untilDateInt:
        result = 0
        for i in range(1, of_index):
            #if "w" in parts[i]:
            #    result += int(parts[i].replace("w", "")) * 3600 * 8 * 5 # or `* 7`?
            if "d" in parts[i]:
                result += int(parts[i].replace("d", "")) * 3600 * 8
            if "h" in parts[i]:
                result += int(parts[i].replace("h", "")) * 3600
            if "m" in parts[i]:
                result += int(parts[i].replace("m", "")) * 60
        return result
    else:
        return 0


def format_date(date: str):
    if date is None:
        return ''
    if len(date) < 10:
        return date
    return date[:10]


def write_file(msg: str):
    with open('test.txt', 'w') as f:
        f.write("%s\n" % msg)


def loadIssueInfo(issue: TicketInfo):
    global total_seconds
    print("fetch issue %s" % issue.number)
    pageNum = 1
    while True:
        print('  fetch page %s' % pageNum)
        response = s.get('{}/projects/{}/issues/{}/discussions?per_page=100&page={}'.format(
            config.base_url, issue.project_id, issue.number, pageNum), headers={'PRIVATE-TOKEN': config.api_token})
        try:
            discussions = response.json()
        except:
            write_file(response.content)
            raise
        if 'message' in discussions and discussions['message'] == "404 Not found":
            break
        if discussions:
            for discussion in discussions:
                if 'notes' in discussion:
                    for note in discussion['notes']:
                        if note['author']['username'] == config.user_name and note['body'][:6] == "added " \
                                and " of time spent at " in note['body']:
                            seconds = parseTimeSpent(note['body'], sinceDateInt, untilDateInt)
                            if seconds > 0:
                                total_seconds += seconds
                                workitems.append({
                                    'issue': issue.number,
                                    'created': note['created_at'],
                                    'time': seconds / 3600
                                })
                else:
                    print(discussion)
                    break
            pageNum += 1
        else:
            break


def extractTicket(commitTitle: str):
    if 'Merge branch' == commitTitle[:12]:
        return None
    if 'Merge remote' == commitTitle[:12]:
        return None
    if commitTitle.strip()[0] == '#':
        return int(commitTitle.split('-')[0].strip()[1:].strip())
    else:
        print("WARN: commit without ticket number: {}".format(commitTitle))
        return None


def loadTicketsFromCommits(since: str, until: str):
    print("fetch commits")
    pageNum = 1
    result = {}
    commits = None
    for project_id in config.projects:
        print('fetch commits for project %s' % project_id)
        while True:
            print('  fetch page %s' % pageNum)
            response = s.get(
                '{}/projects/{}/repository/commits?per_page=100&page={}&since={}T00:00:00&until={}T23:59:59'.format(
                    config.base_url, project_id, pageNum, since, until),
                headers={'PRIVATE-TOKEN': config.api_token})
            try:
                commits = response.json()
            except:
                write_file(response.content)
                raise
            if 'message' in commits and commits['message'] == "404 Not found":
                break
            if commits:
                for commit in commits:
                    if 'author_email' in commit:
                        if commit['author_email'].lower() in config.authors:
                            ticketNumber = extractTicket(commit['title'])
                            if not (ticketNumber is None):
                                ticketInfo = result[ticketNumber] if ticketNumber in result else TicketInfo(ticketNumber, project_id, set())
                                ticketInfo.dates.add(dateToInt(commit['created_at']))
                                result[ticketNumber] = ticketInfo
                    else:
                        # something strange - commit without author?
                        break
                pageNum += 1
            else:
                break
    return result  # map<ticket, TicketInfo>


if __name__ == "__main__":

    total_seconds = 0

    config = JsonSlurper.create(
        file_name="local.settings.json" if os.path.exists("local.settings.json") else "settings.json"
    )

    # Note: both dates are inclusive
    sinceDateInt = dateToInt(config.since_date)
    untilDateInt = dateToInt(config.until_date)

    workitems = []

    s = requests.Session()
    # Sometimes Gitlab is unstable, and also has load limits
    retries = Retry(total=8,
                    backoff_factor=0.4,
                    status_forcelist=[500, 502, 503, 504, 429])
    s.mount('http://', HTTPAdapter(max_retries=retries))
    s.mount('https://', HTTPAdapter(max_retries=retries))

    tickets = loadTicketsFromCommits(config.since_date, config.until_date)
    pool = ThreadPool(config.threads)
    results = pool.map(loadIssueInfo, tickets.values())
    pool.close()
    pool.join()

    workitems.sort(key=lambda wi: wi['issue'])
    print('-' * 80)
    for workitem in workitems:
        ticketNumber = workitem['issue']
        print('{}\t{}\t{}'.format(ticketNumber, format_date(workitem['created']), workitem['time']))
    print('-' * 80)
    print('{} total spent {} h'.format(config.user_name, total_seconds / 3600))

    filename = 'timespent_%s_%s.xlsx' % (config.since_date, config.until_date)
    workbook = xlsxwriter.Workbook(filename)
    worksheet = workbook.add_worksheet()
    hours_format = workbook.add_format({'num_format': '#,##0.000'})
    bold_format = workbook.add_format({'bold': True})
    worksheet.write(0, 0, 'Time spent since %s till %s' % (config.since_date, config.until_date), bold_format)

    row = 3
    worksheet.write(2, 0, 'Ticket', bold_format)
    worksheet.write(2, 1, 'Date', bold_format)
    worksheet.write(2, 2, 'Time Spent', bold_format)
    for workitem in workitems:
        ticketNumber = workitem['issue']
        spentAt = format_date(workitem['created'])
        amountOfTime = workitem['time']
        worksheet.write(row, 0, ticketNumber)
        worksheet.write(row, 1, spentAt)
        worksheet.write(row, 2, amountOfTime, hours_format)
        row = row + 1

    worksheet.write(row, 0, 'Total:', bold_format)
    worksheet.write(row, 2, '=SUM(C{}:C{})'.format(4, row), hours_format)
    worksheet.set_column(0, 0, 10)
    worksheet.set_column(1, 1, 20)
    worksheet.set_column(2, 2, 10)
    workbook.close()
    os.system('start %s' % filename)

    # check: there are commits on this day but no time spent
    for workitem in workitems:
        spentAt = dateToInt(workitem['created'])
        ticketNumber = workitem['issue']
        if spentAt in tickets[ticketNumber].dates:
            tickets[ticketNumber].dates.remove(spentAt)
        else:
            print("Warn: Ticket {}: time spent but no commits: {}".format(ticketNumber, spentAt))

    for ticket in tickets:
        dates_without_spent_time = tickets[ticket].dates
        if len(dates_without_spent_time) > 0:
            print("Warn: Ticket: {}: there are commits but no time spent: {}".format(ticket, dates_without_spent_time))

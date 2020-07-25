# gitlab-timespent
Tool to collect all time spent comments in Gitlab projects


Gitlab TimeSpent is a console tool that I use to generate timesheet report for Gitlab projects.
As the output, the tool generates a report in Excel format.

![Excel report screenshot](https://github.com/xuthus/gitlab-timespent/raw/master/docs/excel1.png "Excel report screenshot")

All settings are stored in `settings.json` file.

Settings

| Setting   |      Meaning      |  Example |
|----------|-------------|------|
| threads | Maximum threads amount used to fetch data from Gitlab repository | 10 |
| api_token | Gitlab API token - replace with your own | ?? |
| base_url | Gitlab rest api url, probably will not change | "https://gitlab.com/api/v4" |
| projects | Array of project ids you want to scan | 123456, 123457 |
| user_name | Your user name (used to filter comments) | "programmador1" |
| authors | Array of your emails used to author commits (I have different emails for GitHub and GitLab, so sometimes I commit under wrong user) | "user1@domain1.com", "user2@domain2.com" |
| since_date | Begin of date range. Use format YYYY-MM-DD | "2020-05-01" |
| until_date | End of date range. Use format YYYY-MM-DD | "2020-05-31" |

> Note: both of dates are inclusive. So to generate month report you should specify first and last days of the month.

> Note: tickets where the user doesn't have merged MRs are not counted!

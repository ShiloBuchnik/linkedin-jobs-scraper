![Not available](https://i.imgur.com/KCkWYrO.png)
### This is ~~not~~ a small [LinkedIn](https://www.linkedin.com) jobs bot, written in Python3

Let's say, hypothetically, that I were to write a web-scraper that retrieves job listings on LinkedIn,  
utilising Beautiful Soup and Selenium.  
Then, let's assume this tool also filters those jobs based on country and keywords.  
Therefore , this repo hosts the theoretical script that would be written in the aforementioned hypothetical.

The (theoretical) script creates a save file 'jobs.csv' to keep track of jobs seen in previous run,  
so that in the next run of the script, new jobs will appear first.

In main, you can change 'job_titles', 'country' and 'keywords' to the values you wish (case-insensitive).  
The script would only display job listings whose titles contain one of the keywords.  
  
*Note that it only displays results from the public 'jobs' page, and not the unique one that requires login.

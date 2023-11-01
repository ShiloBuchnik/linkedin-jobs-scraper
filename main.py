from bs4 import BeautifulSoup  # For searching in HTML file
from colorama import Fore  # For coloring output text
import csv

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time

# Returns the string with 'color' "appended" to it
def getColoredString(string, color):
	return color + string + Fore.RESET

class Job:
	def __init__(self, content, company_name, upload_time, href):
		self.content = content
		self.company_name = company_name
		self.upload_time = upload_time
		self.href = href

	def print(self):
		print(getColoredString("Job's title: ", Fore.RED) + self.content + \
		getColoredString(" Company name: ", Fore.RED) + self.company_name + getColoredString(" Upload time: ", Fore.RED) + \
		self.upload_time + getColoredString(" Link: ", Fore.RED) + self.href)

	def __eq__(self, obj):
		return True if self.content == obj.content and self.company_name == obj.company_name else False

# How we handle infinite scrolling
def scrollUntilBottom(driver):
	last_total_height = driver.execute_script("return document.body.scrollHeight")  # Returns total height of 'body' element
	while True:
		driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")  # Running JS to scroll to bottom
		time.sleep(1)  # Let the page load properly. Using 'sleep' instead of 'wait' is acceptable here
		curr_total_height = driver.execute_script("return document.body.scrollTop")
		if last_total_height == curr_total_height: # When our scrolling hasn't changed the height, we know we've reached the bottom
			break

		last_total_height = curr_total_height


# Returns true iff 'string' contains one of the words in 'words_list', while IGNORING CASE.
def stringContains(string, words_list):
	string = string.lower()
	for word in words_list:
		word = word.lower()
		if word in string:
			return True

	return False

# Gets HTML from URL, and gets all 'div' elements that represents jobs in the webpage.
def getRawJobs(driver, urls_list):
	divs_elements = []
	for url in urls_list:
		driver.get(url)
		scrollUntilBottom(driver)

		soup = BeautifulSoup(driver.page_source, 'html.parser')
		with open("test.html", "w", encoding="utf-8") as file:
			file.write(driver.page_source)
		divs_elements.extend(soup.find_all("div", class_="base-card"))  # That element has several classes. We only write one of them

	# Returning a list of <div>s that represent jobs. We extract from that the needed information
	return divs_elements

# Sadly, we can't use the 'datetime' field in the time element, since it only stores dates without hours (example: '2023-10-17').
# We want our sorting to be precise, so we have to work with the time element's content (example: '3 days ago').
# For that we create a sorting key function, to pass to 'sort'
def sortKey(div_element):
	upload_time = div_element.find("time").text.strip()
	first_space_index = upload_time.index(' ')
	time_unit = upload_time.split()[1] # Can be 'minutes', 'hours', 'days', 'months' or 'weeks'
	num_of_units = int(upload_time[:first_space_index]) # Number of 'minutes', 'hours', 'days', 'months' or 'weeks'

	# We use 'in' instead of '==' because 'time_unit' could be "minute" or "minutes", for example
	if "minute" in time_unit: # Range [1,59]
		return num_of_units
	elif "hour" in time_unit: # Range: [60,82]
		return 59 + num_of_units
	elif "day" in time_unit: # Range: [83,111]
		return 82 + num_of_units
	elif "week" in time_unit: # Range [112,114]
		return 111 + num_of_units
	elif "month" in time_unit: # Range: [114,125]
		return 114 + num_of_units
	else:
		raise Exception("Faulty time unit: " + time_unit)

# Takes the "raw" list of 'div' elements from before, and creates a list of formatted strings, each represent a job.
# In the process we only select the jobs *whose title contains at least one of the keywords in 'keywords_list'*
def rawJobsToFormattedJobs(divs_elements, keywords_list):
	formatted_jobs = []
	divs_elements.sort(key = sortKey) # We want to print in descending order

	for div in divs_elements:
		first_a_element, second_a_element = div.find_all("a")

		content = first_a_element.text
		content = content.strip()
		# If the job's title doesn't contain one of the keywords, we don't care and move on
		if not stringContains(content, keywords_list):
			continue

		company_name = second_a_element.text
		company_name = company_name.strip()
		if company_name == "Stratasys":
			print("hello")

		time_element = div.find("time")
		upload_time = time_element.text # Approximate time of upload. For example "3 hours ago"
		upload_time = upload_time.strip()

		href = first_a_element.get("href")
		index = href.find('?')
		if index != -1: # Removes the query string from the URL, if present
			href = href[:index]

		curr_job = Job(content, company_name, upload_time, href)
		formatted_jobs.append(curr_job)

	return formatted_jobs

def main():
	jobs_urls = ["https://www.linkedin.com/jobs/search?keywords=student%20software&location=Israel"]

	keywords_list = ["student", "intern"]

	options = Options()
	# Disabling loading images, to make the script run faster.
	options.add_argument('--blink-settings=imagesEnabled=false')
	driver = webdriver.Chrome(options)
	#driver.minimize_window()

	while True:
		driver.get("https://www.linkedin.com/jobs/search?keywords=student%20software&location=Israel")
		time.sleep(2)

	exit(1)

	divs_elements = getRawJobs(driver, jobs_urls)
	divs_elements.extend
	time.sleep(4)
	driver.quit()

	all_curr_jobs = rawJobsToFormattedJobs(divs_elements, keywords_list)

	try:
		with open("jobs.csv", 'r') as file:
			reader = csv.reader(file)  # Get 'reader' object
			old_jobs = [row[3] for row in reader] # 'old_jobs' is now a list of hrefs
	except FileNotFoundError:
		old_jobs = None

	if old_jobs:
		added_jobs_href_set = set([job.href for job in all_curr_jobs]) - set(old_jobs)
		added_jobs, unchanged_jobs = [], []
		for job in all_curr_jobs:
			if job.href in added_jobs_href_set:
				added_jobs.append(job)
			else:
				unchanged_jobs.append(job)

		print(Fore.GREEN + f"Added jobs since last run of the script ({len(added_jobs)}):" + Fore.RESET)
		for job in added_jobs:
			job.print()

		print(Fore.GREEN + f"Unchanged jobs since last run of the script ({len(unchanged_jobs)}):" + Fore.RESET)
		for job in unchanged_jobs:
			job.print()
	else:
		print(Fore.GREEN + f"List of available jobs ({len(all_curr_jobs)}):" + Fore.RESET)
		for job in all_curr_jobs:
			job.print()

	with open("jobs.csv", 'w', newline='') as file: # 'csv' already adds newlines in the file, so we set 'newline' to nothing
		writer = csv.writer(file)  # Get 'writer' object
		writer.writerows([(job.content, job.company_name, job.upload_time, job.href) for job in all_curr_jobs])


if __name__ == '__main__':
	main()
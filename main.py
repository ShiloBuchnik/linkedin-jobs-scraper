from bs4 import BeautifulSoup  # For searching in HTML file
from colorama import Fore  # For coloring output text
import csv # For handling csv files
import time
from datetime import timedelta

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException

# Returns colored version of the given string
def getColoredString(string: str, color) -> str:
	return color + string + Fore.RESET

class Job:
	def __init__(self, content: str, location: str, upload_time: str, company_name: str, href: str, timedelta_obj: timedelta):
		self.content = content
		self.location = location
		self.upload_time = upload_time
		self.timedelta_obj = timedelta_obj
		self.company_name = company_name
		self.href = href

	def print(self):
		print(getColoredString("Job's title: ", Fore.RED) + self.content + getColoredString(" Location: ", Fore.RED) +
		self.location + getColoredString(" Upload time: ", Fore.RED) + self.upload_time +
		getColoredString(" Company name: ", Fore.RED) + self.company_name + getColoredString(" Link:\n", Fore.RED) + self.href + "\n")

	# In order to store Job objects in a set, we need to define two methods:
	# 1) __hash__: simply because all elements in a set must be hashable, since it is simply a hash-table
	# 2) __eq__: When we insert an element into a set, we need to know if it's already equal to an existing element.
	# The default implementation is to return true iff the objects are literally the same in memory.
	# We want to change that - two objects are the same iff their href is the same
	def __eq__(self, obj):
		return True if self.href == obj.href else False

	def __hash__(self):
		return hash((self.content, self.location, self.upload_time, self.company_name, self.href))

	# We want the tuple() built-in function to work on Job objects (convert them to tuples).
	# For that we need to make our object an iterable, and we do that by defining '__iter__'. We define it as a generator function.
	def __iter__(self):
		yield self.content
		yield self.location
		yield self.upload_time
		yield self.company_name
		yield self.href

# How we handle infinite scrolling
def scrollUntilBottom(driver) -> None:
	last_total_height = driver.execute_script("return document.body.scrollHeight")  # Returns total height of 'body' element's content
	while True:
		driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")  # Running JS to scroll to bottom
		time.sleep(1)  # Let the page load properly. Using 'sleep' instead of 'wait' is acceptable here
		curr_total_height = driver.execute_script("return document.body.scrollHeight")
		if last_total_height == curr_total_height: # When our scrolling hasn't changed the content's height, we know we've reached the bottom
			break

		last_total_height = curr_total_height

# There's a lot of happening here, because of LinkedIn shitty anti-scraping policy.
# First, sometimes it'll show only part of the actual job results on a page visit, so we visit every page *twice*.
# Second, sometimes it'll redirect us to a login page instead of the webpage.
# For that we put 'try except' block in an infinite loop, basically requesting the page until we get what we want.
# We check if we got to the real page by waiting for a 'div.base-card' element to be visible.
# If it's not the real page, the element won't appear, and it throws 'TimeoutException'.

# Also, we alert the user when a job title is not valid, by waiting for an element that shows up only in the "invalid job title" page
def getPageAndScroll(driver, wait, url: str) -> None:
	while True:
		try:
			driver.get(url)
			try:
				wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "h1.core-section-container__main-title")))
				print(Fore.RED + "Program ran into an invalid job title that generated following URL: " + Fore.RESET + url)
				exit(-1)
			except TimeoutException:
				pass

			wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "div.base-card")))
			scrollUntilBottom(driver)
			break
		except TimeoutException:
			pass

# Gets HTML from URL, and gets all 'div' elements that represents jobs in the webpage.
def getRawJobs(driver, urls_list: list[str]) -> set:
	divs_elements = set() # {} means an empty dict, so we use 'set()' instead
	wait = WebDriverWait(driver, 0.5)

	for i in range(2):
		for url in urls_list:
			getPageAndScroll(driver, wait, url)

			soup = BeautifulSoup(driver.page_source, 'html.parser')
			divs_elements.update(soup.find_all("div", class_="base-card")) # That element has several classes. We only write one of them
	# Returning a set of <div>s that represent jobs.
	return divs_elements

# Converts strings like "7 days ago" into a datetime object
def StrToDatetimeObject(upload_time: str) -> timedelta:
	parts = upload_time.split()
	quantity = int(parts[0])  # For example: '7'
	unit = parts[1]  # For example: 'days'

	if unit == 'minute' or unit == 'minutes':
		return timedelta(minutes=quantity)
	elif unit == 'hour' or unit == 'hours':
		return timedelta(hours=quantity)
	elif unit == 'day' or unit == 'days':
		return timedelta(days=quantity)
	elif unit == 'week' or unit == 'weeks':
		return timedelta(weeks=quantity)
	elif unit == 'month' or unit == 'months':
		return timedelta(days=quantity*30)  # 'timedelta()' doesn't have a 'months' argument, so we approximate using 'days'
	else:
		raise ValueError(f"Unexpected time unit: {unit}")

# Takes the "raw" set of 'div' elements from before, and creates a set of Job objects, each contains the relevant information.
# In the process we only select the jobs *whose title contains at least one of the keywords in 'keywords_list'*
def rawJobsToFormattedJobs(divs_elements: set, keywords: list[str], cutoff_time_in_months: int, forbidden_words: list[str]) -> set[Job]:
	formatted_jobs = set()

	for div in divs_elements:
		first_a_element, second_a_element = div.find_all("a")
		content = first_a_element.text # Gets content of element
		content = content.strip()
		# If the job's title doesn't contain at least one of the keywords (ignoring case),
		# or it contains one of the forbidden words, we don't care and move on
		# We pass a generator expression, such that each keyword turns into a boolean that represents whether it's contained in keywords_list
		if not any( (keyword.lower() in content.lower()) for keyword in keywords ) or \
			any( (forbidden.lower() in content.lower()) for forbidden in forbidden_words ):
			continue

		location = div.find("span", class_="job-search-card__location").text # Finds *element* inside <div> element
		location = location.strip()
		index = location.find(',')
		if index != -1: # Extract only the city's name. Sometimes it just says 'Israel', so there won't be a comma
			location = location[:index]

		company_name = second_a_element.text
		company_name = company_name.strip()

		upload_time = div.find("time").text
		upload_time = upload_time.strip()

		timedelta_obj = StrToDatetimeObject(upload_time) # We'll use this object to sort later
		if timedelta(days=cutoff_time_in_months * 30) < timedelta_obj: # If a job listing is too old, we don't care and move on
			continue

		href = first_a_element.get("href") # Finds *field* of <a> element
		index = href.find('?')
		if index != -1: # Removes the query string from the URL, if present
			href = href[:index]

		curr_job = Job(content, location, upload_time, company_name, href, timedelta_obj)
		formatted_jobs.add(curr_job)

	return formatted_jobs

def printSets(all_curr_jobs: set[Job], old_jobs: set[Job]) -> None:
	added_jobs = all_curr_jobs - old_jobs  # If file not found, then old_jobs is empty, so added_jobs == all_curr_jobs.
	unchanged_jobs = all_curr_jobs - added_jobs

	if old_jobs:
		print(Fore.GREEN + f"Added jobs since last run of the script ({len(added_jobs)}):" + Fore.RESET)
	else:
		print(Fore.GREEN + f"List of available jobs ({len(added_jobs)}):" + Fore.RESET)

	# We sort by the job's datetime field.
	for job in sorted(added_jobs, key=lambda job_arg: job_arg.timedelta_obj):
		job.print()

	if old_jobs:
		print(Fore.GREEN + f"Unchanged jobs since last run of the script ({len(unchanged_jobs)}):" + Fore.RESET)
		for job in sorted(unchanged_jobs, key=lambda job_arg: job_arg.timedelta_obj):
			job.print()

# Convert title like "Junior Software Engineer" to a valid URL like
# "https://www.linkedin.com/jobs/search?keywords=Junior%20Software%20Engineer&location=Israel"
def jobTitlesToJobUrls(job_titles: list[str], country: str) -> list[str]:
	job_urls = []

	for title in job_titles:
		curr_str = "https://www.linkedin.com/jobs/search?keywords="
		words = [word + "%20" for word in title.split()]
		words[-1] = words[-1][:-3]  # Removing the '%20' from last word

		curr_str += ''.join(words)
		curr_str += "&location=" + country
		job_urls.append(curr_str)

	return job_urls

def main() -> None:
	""" User Defined Variables """
	job_titles = ["Junior Software", "Junior Software Engineer", "Junior Software Developer"]
	country = "Israel"
	keywords = ["Junior", "Intern"]
	forbidden_words = ["QA", "Test", "Automation", "IT", "Help", "Support", "Customer"]
	cutoff_time_in_months = 2 # Won't show listings older than the number stored in here


	print("Running, please wait...")
	job_urls = jobTitlesToJobUrls(job_titles, country)

	options = Options()
	options.add_argument("--headless=new") # If you want to see the driver in action (for debugging purposes), comment this line
	options.add_argument("--disable-gpu") # Helps a bit with performance
	options.add_argument("--lang=en-US") # Forces the listings to be in english, so the code functions properly
	driver = webdriver.Chrome(options)

	divs_elements = getRawJobs(driver, job_urls)
	driver.close()
	all_curr_jobs = rawJobsToFormattedJobs(divs_elements, keywords, cutoff_time_in_months, forbidden_words)

	try:
		with open("jobs.csv", 'r') as file:
			reader = csv.reader(file)
			old_jobs = {Job(row[0], row[1], row[2], row[3], row[4], StrToDatetimeObject(row[2])) for row in reader}
	except FileNotFoundError:
		old_jobs = set()

	printSets(all_curr_jobs, old_jobs)

	with open("jobs.csv", 'w', newline='') as file: # 'csv' already adds newlines in the file, so we set 'newline' to nothing
		writer = csv.writer(file)
		writer.writerows([tuple(job) for job in all_curr_jobs])

	input("Press any key...")


if __name__ == '__main__':
	main()

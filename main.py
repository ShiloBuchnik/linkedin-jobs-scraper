from bs4 import BeautifulSoup  # For searching in HTML file
from colorama import Fore  # For coloring output text
import csv # For handling csv files
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException

# Returns colored version of the given string
def getColoredString(string, color):
	return color + string + Fore.RESET

class Job:
	def __init__(self, content, location, upload_time, company_name, href):
		self.content = content
		self.location = location
		self.upload_time = upload_time
		self.company_name = company_name
		self.href = href

	def print(self):
		print(getColoredString("Job's title: ", Fore.RED) + self.content + getColoredString(" Location: ", Fore.RED) +
		self.location + getColoredString(" Upload time: ", Fore.RED) + self.upload_time +
		getColoredString(" Company name: ", Fore.RED) + self.company_name + getColoredString(" Link: ", Fore.RED) + self.href)

	# In order to store Job objects in a set, we need to define two methods:
	# 1) __hash__: simply because all elements in a set must be hashable, since it is simply a hash-table
	# 2) __eq__: When we insert an element into a set, we need to know if it's already equal to an existing element.
	# The default implementation is to return true iff the objects are literally the same in memory.
	# We want to extend that - two objects are the same iff their href is the same
	def __eq__(self, obj):
		return True if self.href == obj.href else False

	def __hash__(self):
		return hash((self.content, self.location, self.upload_time, self.company_name, self.href))

	# We want the tuple() built-in to work on Job objects (convert them to tuples).
	# For that we need to make our object an iterable, and we do that by defining '__iter__'. We define it as a generator function.
	def __iter__(self):
		yield self.content
		yield self.location
		yield self.upload_time
		yield self.company_name
		yield self.href

# How we handle infinite scrolling
def scrollUntilBottom(driver):
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
def getPageAndScroll(driver, wait, url):
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
def getRawJobs(driver, urls_list):
	divs_elements = set() # {} means an empty dict, so we use 'set()' instead
	wait = WebDriverWait(driver, 0.5)

	for i in range(2):
		for url in urls_list:
			getPageAndScroll(driver, wait, url)

			soup = BeautifulSoup(driver.page_source, 'html.parser')
			divs_elements.update(soup.find_all("div", class_="base-card")) # That element has several classes. We only write one of them

	# Returning a set of <div>s that represent jobs.
	return divs_elements

# Returns true iff 'string' contains one of the words in 'words_list', while IGNORING CASE.
def stringContains(string, words_list):
	string = string.lower()
	for word in words_list:
		word = word.lower()
		if word in string:
			return True

	return False

# Takes the "raw" set of 'div' elements from before, and creates a set of Job objects, each contains the relevant information.
# In the process we only select the jobs *whose title contains at least one of the keywords in 'keywords_list'*
def rawJobsToFormattedJobs(divs_elements, keywords_list):
	formatted_jobs = set()

	for div in divs_elements:
		try: # Temporary, until I debug this pesky 'valueError' exception
			first_a_element, second_a_element = div.find_all("a")
		except ValueError:
			with open("test.html", "w") as file:
				file.write(div)
			exit(-1)

		content = first_a_element.text # Gets content of element
		content = content.strip()
		# If the job's title doesn't contain one of the keywords, we don't care and move on
		if not stringContains(content, keywords_list):
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

		href = first_a_element.get("href") # Finds *field* of <a> element
		index = href.find('?')
		if index != -1: # Removes the query string from the URL, if present
			href = href[:index]

		curr_job = Job(content, location, upload_time, company_name, href)
		formatted_jobs.add(curr_job)

	return formatted_jobs

# Sadly, we can't use the 'datetime' field in the time element, since it only stores dates without hours (example: '2023-10-17').
# We want our sorting to be precise, so we have to work with the time element's content (example: '3 days ago').
# For that we create a sorting key function, to pass to 'sort'
def sortKey(job):
	first_space_index = job.upload_time.index(' ')
	time_unit = job.upload_time.split()[1] # Can be 'minutes', 'hours', 'days', 'weeks' or 'months'
	num_of_units = int(job.upload_time[:first_space_index]) # Number of 'minutes', 'hours', 'days', 'weeks' or 'months'

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

def printSets(all_curr_jobs, old_jobs):
	added_jobs = all_curr_jobs - old_jobs  # If file not found, then old_jobs is empty, so added_jobs == all_curr_jobs.
	unchanged_jobs = all_curr_jobs - added_jobs

	if old_jobs:
		print(Fore.GREEN + f"Added jobs since last run of the script ({len(added_jobs)}):" + Fore.RESET)
	else:
		print(Fore.GREEN + f"List of available jobs ({len(added_jobs)}):" + Fore.RESET)

	for job in sorted(added_jobs, key=sortKey):
		job.print()

	if old_jobs:
		print(Fore.GREEN + f"Unchanged jobs since last run of the script ({len(unchanged_jobs)}):" + Fore.RESET)
		for job in sorted(unchanged_jobs, key=sortKey):
			job.print()

def jobTitlesToJobUrls(job_titles, country):
	job_urls = []
	# Convert title like "Student Software Engineer" to a valid URL like
	# "https://www.linkedin.com/jobs/search?keywords=Student%20Software%20Engineer&location=Israel"
	for title in job_titles:
		curr_str = "https://www.linkedin.com/jobs/search?keywords="
		words = [word + "%20" for word in title.split()]
		words[-1] = words[-1][:-3]  # Removing the '%20' from last word

		curr_str += ''.join(words)
		curr_str += "&location=" + country
		job_urls.append(curr_str)

	return job_urls

def main():
	job_titles = ["Student Software", "Student Software Engineer"]
	country = "Israel"
	keywords_list = ["student", "intern", "סטודנט"]

	print("Running, please wait...")
	job_urls = jobTitlesToJobUrls(job_titles, country)

	options = Options()
	options.add_argument("--headless=new") # If you want to see the driver in action (for debugging purposes), comment this line
	options.add_argument("--disable-gpu") # Helps a bit with performance
	driver = webdriver.Chrome(options)

	start = time.time()
	divs_elements = getRawJobs(driver, job_urls)
	driver.close()
	print(time.time() - start)
	all_curr_jobs = rawJobsToFormattedJobs(divs_elements, keywords_list)

	try:
		with open("jobs.csv", 'r') as file:
			reader = csv.reader(file)
			old_jobs = {Job(row[0], row[1], row[2], row[3], row[4]) for row in reader}
	except FileNotFoundError:
		old_jobs = set()

	printSets(all_curr_jobs, old_jobs)

	with open("jobs.csv", 'w', newline='') as file: # 'csv' already adds newlines in the file, so we set 'newline' to nothing
		writer = csv.writer(file)
		writer.writerows([tuple(job) for job in all_curr_jobs])

	input("Press any key...")


if __name__ == '__main__':
	main()
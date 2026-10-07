import undetected_chromedriver as uc
from webdriver_manager.chrome import ChromeDriverManager
from time import sleep
import os
from scrapy import Selector
import csv
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select
import string
import random

# Oakland now uses reCAPTCHA Enterprise v3 (invisible, score based). The page itself calls
# grecaptcha.enterprise.execute() when Search is clicked and overwrites the hidden token field,
# so an injected 2Captcha token is never used. Instead we run an undetected Chrome so the
# browser's own token scores above Oakland's threshold, and retry when it doesn't.

MAX_SEARCH_ATTEMPTS = 8

dataFile = 'Oakland_County_Data.csv'

def typeLikeHuman(xpath, text):
    element = WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.XPATH, xpath)))
    element.click()
    for ch in text:
        element.send_keys(ch)
        sleep(random.uniform(0.08, 0.25))
    sleep(random.uniform(0.5, 1.2))

with open('inputFile.txt', 'r') as file:
    lines = file.readlines() 
    for line in lines:
        if "startYear" in line:
            startYear = line.split('=')[1].strip()
        if "endYear" in line:
            endYear = line.split('=')[1].strip()


csv.field_size_limit(5000000)
list_of_rows = []
if os.path.exists(dataFile):
    with open(dataFile, 'r', encoding="utf-8-sig") as read_obj:
        csv_reader = csv.reader(read_obj)
        list_of_rows = list(csv_reader)

# Case numbers already in the CSV. Each case shows up once per party in the search results
# (and again under the other party's letter), so this also stops a case being scraped twice in one run
scrappedCases = {row[0].strip() for row in list_of_rows if row and row[0].strip() not in ('', 'Case Number')}

alphabet = string.ascii_lowercase

def botInitialization():
    # Initialize the Bot
    # Do NOT run headless, it gets a low reCAPTCHA score
    chromeOptions = uc.ChromeOptions()
    chromeOptions.add_argument("--start-maximized")

    # webdriver_manager detects the installed Chrome version and downloads the matching chromedriver
    try:
        chromedriver_path = ChromeDriverManager().install()
    except Exception as e:
        print('webdriver_manager could not get chromedriver, letting undetected_chromedriver download it:', e)
        chromedriver_path = None

    driver = uc.Chrome(options=chromeOptions, driver_executable_path=chromedriver_path)
    driver.maximize_window()
    driver.execute_script("window.open('', '_blank');")
    driver.switch_to.window(driver.window_handles[0])
    return driver

driver = botInitialization()


def runSearch(letter):
    # Returns True once the results table loads, False if Oakland rejected the reCAPTCHA score
    startURL = 'https://courtexplorer.oakgov.com/OaklandCounty'
    driver.get(startURL)

    WebDriverWait(driver, 60).until(EC.element_to_be_clickable((By.XPATH, "//button[@id='btnAdvancedSearch']")))
    sleep(random.uniform(3, 6))

    advancedSearchButton = driver.find_element(By.XPATH, "//button[@id='btnAdvancedSearch']")
    advancedSearchButton.click()
    WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.XPATH, "//input[@id='txtLastName']")))
    sleep(1)

    typeLikeHuman("//input[@id='txtLastName']", letter)
    typeLikeHuman("//input[@id='txtCaseYearfrom']", startYear)
    typeLikeHuman("//input[@id='txtCaseYearthrough']", endYear)
    typeLikeHuman("//input[@id='txtCaseTypefrom']", 'DM')
    typeLikeHuman("//input[@id='txtCaseTypethrough']", 'DO')
    sleep(random.uniform(2, 4))

    # The page's own click handler fetches the reCAPTCHA v3 token and submits the form
    searchButton = driver.find_element(By.XPATH, "//button[@id='btnCircuitSubmit']")
    searchButton.click()

    try:
        WebDriverWait(driver, 40).until(
            lambda d: d.find_elements(By.XPATH, "//table[@id='datatable_caselist']")
            or 'below threshold' in d.page_source.lower()
        )
    except:
        return False

    if 'below threshold' in driver.page_source.lower():
        return False
    return True



writeHeader = not list_of_rows

with open(dataFile, 'a', newline='', encoding="utf-8-sig") as csvfile:
    fieldnames = [
        'Case Number',
        'File Date',
        'Case Judge',
        'Docket Info',
        'Party Type',
        'Party Name',
        'Attorney Name',
        'Disposition Text',
        'Disposition Date'
    ]

    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    if writeHeader:
        writer.writeheader()

    for letter in alphabet:

        searchPassed = False
        for attempt in range(1, MAX_SEARCH_ATTEMPTS + 1):
            try:
                searchPassed = runSearch(letter)
            except Exception as e:
                print(f'Search error for "{letter}":', e)
                searchPassed = False

            if searchPassed:
                break

            print(f'reCAPTCHA score too low for "{letter}" (attempt {attempt}/{MAX_SEARCH_ATTEMPTS}), retrying..')
            sleep(random.uniform(15, 30))

        if not searchPassed:
            print(f'Skipping "{letter}", search kept failing.')
            continue

        while True:
            WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.XPATH, "//table[@id='datatable_caselist']")))
            sleep(5)

            try:
                recordsPerPageSelector = driver.find_element(By.XPATH, "//select[@name='datatable_caselist_length']")
                recordsPerPageSelector = Select(recordsPerPageSelector)
                recordsPerPageSelector.select_by_value('100')
                sleep(3)
            except:
                pass

            response = Selector(text=driver.page_source)

            CASES = response.xpath("//table[@id='datatable_caselist']//tbody/tr[td[1]/a]")

            driver.switch_to.window(driver.window_handles[1])
            for CASE in CASES:

                partyType = partyName = attorneyName = dispositionText = dispositionDate = None

                listedCaseNumber = CASE.xpath("normalize-space(./td[4])").get()
                caseURL = f'https://courtexplorer.oakgov.com{CASE.xpath("./td[1]/a/@href").get()}'

                if listedCaseNumber in scrappedCases:
                    print('Already Scrapped:', listedCaseNumber)
                    continue

                driver.get(caseURL)
                
                WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.XPATH, "//form[@id='CaseDetails']")))
                sleep(5)

                response = Selector(text=driver.page_source)

                caseNumber = response.xpath("//strong[text()='Case Number']//following::div[1]/text()").get()
                if caseNumber:
                    caseNumber = caseNumber.strip()

                fileDate = response.xpath("//strong[text()='Case Filed']//following::div[1]/text()").get()
                if fileDate:
                    fileDate = fileDate.strip()

                caseJudge = response.xpath("//strong[text()='Judge Name']//following::div[1]/text()").get()
                if caseJudge:
                    caseJudge = caseJudge.strip()

                docketInfoText = []

                docketInfoRows = response.xpath("//table[@id='datatable_roalist']/tbody/tr")
                try:
                    docketInfoRows = docketInfoRows[:10]
                except:
                    pass
                
                if docketInfoRows:
                    for docketInfoRow in docketInfoRows:
                        docketInfoDate = docketInfoRow.xpath("./td[1]/text()").get()
                        if docketInfoDate:
                            docketInfoDate = docketInfoDate.strip()

                        docketInfoDescription = docketInfoRow.xpath("./td[3]/text()").get()
                        if docketInfoDescription:
                            docketInfoDescription = docketInfoDescription.strip()

                        value = f'{docketInfoDate}: {docketInfoDescription}'
                        docketInfoText.append(value)

                if docketInfoText:
                    docketInfoText = '; '.join(docketInfoText)

                partyTableSections = response.xpath("//table[@id='datatable_partieslist']/tbody/tr")
                
                if partyTableSections:
                    for partyTableSection in partyTableSections:
                        
                        partyType = partyTableSection.xpath("./td[1]/text()").get()
                        if partyType:
                            partyType = partyType.strip()

                        partyName = partyTableSection.xpath("./td[2]/text()").get()
                        if partyName:
                            partyName = partyName.strip()

                        attorneyName = partyTableSection.xpath("./td[4]/text()").get()
                        if attorneyName:
                            attorneyName = attorneyName.strip()
                            
                        
                        writer.writerow({
                            'Case Number': caseNumber,
                            'File Date': fileDate,
                            'Case Judge': caseJudge,
                            'Docket Info': docketInfoText,
                            'Party Type': partyType,
                            'Party Name': partyName,
                            'Attorney Name': attorneyName,
                            'Disposition Text': dispositionText,
                            'Disposition Date': dispositionDate
                        })

                        print({
                            'Case Number': caseNumber,
                            'File Date': fileDate,
                            'Case Judge': caseJudge,
                            'Docket Info': docketInfoText,
                            'Party Type': partyType,
                            'Party Name': partyName,
                            'Attorney Name': attorneyName,
                            'Disposition Text': dispositionText,
                            'Disposition Date': dispositionDate
                        })

                else:

                    writer.writerow({
                        'Case Number': caseNumber,
                        'File Date': fileDate,
                        'Case Judge': caseJudge,
                        'Docket Info': docketInfoText,
                        'Party Type': partyType,
                        'Party Name': partyName,
                        'Attorney Name': attorneyName,
                        'Disposition Text': dispositionText,
                        'Disposition Date': dispositionDate
                    })

                    print({
                        'Case Number': caseNumber,
                        'File Date': fileDate,
                        'Case Judge': caseJudge,
                        'Docket Info': docketInfoText,
                        'Party Type': partyType,
                        'Party Name': partyName,
                        'Attorney Name': attorneyName,
                        'Disposition Text': dispositionText,
                        'Disposition Date': dispositionDate
                    })

                scrappedCases.add(listedCaseNumber)
                if caseNumber:
                    scrappedCases.add(caseNumber)
                csvfile.flush()

            driver.switch_to.window(driver.window_handles[0])
            sleep(2)

            try:
                nextPageButton = driver.find_element(By.XPATH, "//li[@class='next']/a")
                driver.execute_script("arguments[0].scrollIntoView({block: 'nearest'});", nextPageButton)
                sleep(1)
                driver.execute_script("arguments[0].click();", nextPageButton)
            except:
                break

driver.quit()
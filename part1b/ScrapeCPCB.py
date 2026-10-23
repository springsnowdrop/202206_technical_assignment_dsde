from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import os
import time


webpage = "https://app.cpcbccr.com/ccr/#/caaqm-dashboard-all/caaqm-landing/data"
states = ['West Bengal','Uttar Pradesh']        #define states
cities = ['Kolkata','Lucknow']                  #define cities
file_count = 0
driver = webdriver.Chrome(ChromeDriverManager().install())
driver.maximize_window()

def fill_state_city(driver,webpage,state,city):
    driver.get(webpage)
    flag = 0
    while(flag==0):         #sometimes it takes some retries to access the site
        try:
            WebDriverWait(driver, 10).until(EC.visibility_of_element_located(
                (By.CSS_SELECTOR, "body > app-root > app-caaqm-dashboard > div.container-fluid > div > main > section > app-caaqm-view-data > div > div > div:nth-child(1) > div:nth-child(1) > div > ng-select > div > div > div.toggle"))).click()
            flag=1
        except:
            pass

    # Select relevant state    
    state_button = driver.find_element_by_css_selector("body > app-root > app-caaqm-dashboard > div.container-fluid > div > main > section > app-caaqm-view-data > div > div > div:nth-child(1) > div:nth-child(1) > div > ng-select > select-dropdown > div > div.filter > input")
    state_button.send_keys(state)
    state_button.send_keys(Keys.RETURN)

    # select relevant city
    WebDriverWait(driver, 2).until(EC.visibility_of_element_located(
                (By.CSS_SELECTOR, "body > app-root > app-caaqm-dashboard > div.container-fluid > div > main > section > app-caaqm-view-data > div > div > div:nth-child(1) > div:nth-child(2) > div > ng-select > div > div > div.toggle"))).click()

    city_button = driver.find_element_by_css_selector("body > app-root > app-caaqm-dashboard > div.container-fluid > div > main > section > app-caaqm-view-data > div > div > div:nth-child(1) > div:nth-child(2) > div > ng-select > select-dropdown > div > div.filter > input")
    city_button.send_keys(city)
    city_button.send_keys(Keys.RETURN)
    return driver





if __name__ == "__main__":
    for i in range(2):
        # Get all stations list in the first try by inputting the state and the city
        driver = fill_state_city(driver,webpage,states[i],cities[i])

        WebDriverWait(driver, 2).until(EC.visibility_of_element_located(
                    (By.CSS_SELECTOR, "body > app-root > app-caaqm-dashboard > div.container-fluid > div > main > section > app-caaqm-view-data > div > div > div:nth-child(2) > div:nth-child(1) > div > ng-select > div > div > div.toggle"))).click()

        station_button = driver.find_element_by_css_selector("body > app-root > app-caaqm-dashboard > div.container-fluid > div > main > section > app-caaqm-view-data > div > div > div:nth-child(2) > div:nth-child(1) > div > ng-select > select-dropdown > div > div.filter > input")

        station_list = driver.find_element_by_css_selector("body > app-root > app-caaqm-dashboard > div.container-fluid > div > main > section > app-caaqm-view-data > div > div > div:nth-child(2) > div:nth-child(1) > div > ng-select > select-dropdown > div > div.options > ul").text.split('\n')

        for station in station_list:        # Iterate over the all the stations

            # autofill the state and the city
            driver = fill_state_city(driver,webpage,states[i],cities[i])

            # autofill the station
            WebDriverWait(driver, 2).until(EC.visibility_of_element_located(
                        (By.CSS_SELECTOR, "body > app-root > app-caaqm-dashboard > div.container-fluid > div > main > section > app-caaqm-view-data > div > div > div:nth-child(2) > div:nth-child(1) > div > ng-select > div > div > div.toggle"))).click()

            station_button = driver.find_element_by_css_selector("body > app-root > app-caaqm-dashboard > div.container-fluid > div > main > section > app-caaqm-view-data > div > div > div:nth-child(2) > div:nth-child(1) > div > ng-select > select-dropdown > div > div.filter > input")

            station_button.send_keys(station)

            station_button.send_keys(Keys.RETURN)

            # Autofill the parameters value to PM2.5
            WebDriverWait(driver, 2).until(EC.visibility_of_element_located(
                        (By.CSS_SELECTOR, "body > app-root > app-caaqm-dashboard > div.container-fluid > div > main > section > app-caaqm-view-data > div > div > div:nth-child(2) > div:nth-child(2) > div > div > multi-select > angular2-multiselect > div > div.selected-list > div"))).click()

            parameters = driver.find_element_by_css_selector("body > app-root > app-caaqm-dashboard > div.container-fluid > div > main > section > app-caaqm-view-data > div > div > div:nth-child(2) > div:nth-child(2) > div > div > multi-select > angular2-multiselect > div > div.dropdown-list > div.list-area > ul > li:nth-child(1)").click()


            parameters = driver.find_element_by_css_selector("body > app-root > app-caaqm-dashboard > div.container-fluid > div > main > section > app-caaqm-view-data > div > div > div:nth-child(2) > div:nth-child(2) > div > div > multi-select > angular2-multiselect > div > div.selected-list > div > span").click()


            # Autofill the Year, Month, Date from the Calendar picker
            WebDriverWait(driver, 2).until(EC.visibility_of_element_located(
                        (By.XPATH, "//*[@id='date']/angular2-date-picker/div/div[1]"))).click()

            WebDriverWait(driver, 2).until(EC.visibility_of_element_located(
                        (By.XPATH, "//*[@id='date']/angular2-date-picker/div/div[2]/div[3]/div"))).click()

            WebDriverWait(driver, 2).until(EC.visibility_of_element_located(
                        (By.XPATH, "//*[@id='2020']"))).click()

            WebDriverWait(driver, 2).until(EC.visibility_of_element_located(
                        (By.XPATH, "//*[@id='date']/angular2-date-picker/div/div[2]/div[2]/div"))).click()

            WebDriverWait(driver, 2).until(EC.visibility_of_element_located(
                        (By.XPATH, "//*[@id='JAN']"))).click()


            WebDriverWait(driver, 2).until(EC.visibility_of_element_located(
                        (By.XPATH, "//*[@id='date']/angular2-date-picker/div/div[2]/table[2]/tbody/tr[1]/td[4]/span"))).click()


            # Click on submit button
            driver.find_element_by_css_selector("body > app-root > app-caaqm-dashboard > div.container-fluid > div > main > section > app-caaqm-view-data > div > div > div:nth-child(5) > button").click()
            time.sleep(10)

            # Click 'Save to Excel' and save in .xlsx format
            WebDriverWait(driver, 10).until(EC.visibility_of_element_located(
                        (By.XPATH, "/html/body/app-root/app-caaqm-dashboard/div[1]/div/main/section/app-caaqm-view-data-report/div[2]/div[1]/div[2]/div/div/a[2]/i"))).click()
            time.sleep(60)
            file_count+=1
            
    time.sleep(30)


    driver.close()

    # Move the downloaded files (the most recent ones in ~/Downloads) next to this script
    search_dir = os.path.expanduser("~/Downloads")
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    files = [os.path.join(search_dir, f) for f in os.listdir(search_dir)]
    files = [f for f in files if os.path.isfile(f) and f.endswith(".xlsx")]
    files.sort(key=lambda x: os.path.getmtime(x))

    for f in files[-file_count:]:
        os.replace(f, os.path.join(data_dir, os.path.basename(f)))



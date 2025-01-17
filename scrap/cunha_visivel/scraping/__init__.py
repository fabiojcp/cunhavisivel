import random
import shutil
import time
from loguru import logger
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.chrome.service import Service
from pathlib import Path

from cunha_visivel.workdir.structs import CunhaVisivelDB


class CunhaScraper:
    """
    Gets all PDF download links from the Cunha Imprensa Oficial website.
    """

    def __init__(
        self,
        workdir_op: Path,
        imprensa_oficial_url: str = "https://www.imprensaoficialmunicipal.com.br/",
        cunha_imprensa_oficial_url: str = "https://www.imprensaoficialmunicipal.com.br/cunha",
        pdf_links_css_selector: str = 'a[href^="https://dosp.com.br/impressao.php?i="]',
        headful: bool = False,
        city: str = "cunha",
        url: str = "https://www.imprensaoficialmunicipal.com.br/cunha",
        href: str = 'a[href^="https://dosp.com.br/impressao.php?i="]',
        next_btn: str = "a.next",
        count_existing: bool = False,
    ) -> list[str]:
        self.imprensa_oficial_url = imprensa_oficial_url
        self.cunha_imprensa_oficial_url = cunha_imprensa_oficial_url
        self.pdf_links_css_selector = pdf_links_css_selector
        self.headful = headful
        self.city = city
        self.url = url
        self.href = href
        self.next_btn = next_btn
        self.workdir_op = workdir_op
        self.count_existing = count_existing

    def __contains__(self, url: str):
        return url in self.db.pdf_links

    def extract_edition_text(self, driver, parent):
        try:
            edition_element = parent.find_element(
                By.XPATH, ".//p[b[contains(text(),'Edição:')]]"
            )
            # Use JavaScript to get the text content excluding child elements
            edition_text = driver.execute_script(
                """
                    var element = arguments[0];
                    var childNodes = element.childNodes;
                    var text = '';
                    for (var i = 0; i < childNodes.length; i++) {
                        if (childNodes[i].nodeType === Node.TEXT_NODE) {
                            text += childNodes[i].nodeValue;
                        }
                    }
                    return text;
                """,
                edition_element,
            )
            return edition_text.replace("Edição:", "").strip()
        except NoSuchElementException:
            logger.warning("Element Edição not found.")
            return ""

    def get_pdf_links(self, at_most: int = 0) -> list[dict]:
        """
        Get all PDF download links from the Cunha Imprensa Oficial website.
        """
        chrome_options = webdriver.ChromeOptions()

        if not self.headful:
            chrome_options.add_argument("--headless")

        chrome_options.add_experimental_option(
            "prefs",
            {
                "download.default_directory": "./assets/pdf",
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "safebrowsing.enabled": True,
            },
        )

        # Get the "chromedriver" executable from the PATH
        logger.info("Starting Chrome driver...")
        chromedriver_path = shutil.which("chromedriver")
        driver = webdriver.Chrome(
            options=chrome_options, service=Service(executable_path=chromedriver_path)
        )
        logger.info("Chrome driver started.")

        pdf_links = []

        if self.city != "cunha" and self.url == self.imprensa_oficial_url:
            self.cunha_imprensa_oficial_url = f"{self.imprensa_oficial_url}/{self.city}"

        if self.url != self.cunha_imprensa_oficial_url:
            self.cunha_imprensa_oficial_url = self.url

        if self.href != self.pdf_links_css_selector:
            self.pdf_links_css_selector = self.href

        try:
            logger.info(f'Opening URL "{self.cunha_imprensa_oficial_url}"...')
            driver.get(self.cunha_imprensa_oficial_url)
            logger.info(f'Opened URL "{self.cunha_imprensa_oficial_url}".')

            while True:
                logger.info("Getting PDF links...")
                links = driver.find_elements(
                    By.CSS_SELECTOR, self.pdf_links_css_selector
                )
                logger.info(f"Got {len(links)} PDF links...")
                for link in links:
                    pdf_url = link.get_attribute("href")

                    parent = link.find_element(By.XPATH, "..")
                    name = parent.find_element(By.TAG_NAME, "h3").text
                    date = parent.find_element(
                        By.XPATH, ".//p[b[contains(text(),'Data:')]]"
                    ).text.replace("Data: ", "")
                    year = parent.find_element(
                        By.XPATH, ".//p[b[contains(text(),'Ano:')]]"
                    ).text.replace("Ano: ", "")
                    edition = self.extract_edition_text(driver, parent)
                    # edition = parent.find_element(By.XPATH, ".//p[b[contains(text(),'Edição:')]]").text.replace('Edição: ', '')

                    if not pdf_url in pdf_links:
                        logger.info(f"Adding PDF link: {pdf_url}")

                        pdf_details = {
                            pdf_url: {
                                "name": name,
                                "date": date,
                                "year": year,
                                "edition": edition,
                            }
                        }

                        # Check if the PDF already exists in the workdir
                        if pdf_url in self.workdir_op and not self.count_existing:
                            logger.warning(
                                f"PDF {pdf_url} exists in the workdir, skipping..."
                            )
                            continue

                        pdf_links.append(pdf_details)

                        if at_most > 0 and len(pdf_links) >= at_most:
                            logger.warning(f"Reached the limit of {at_most} PDF links.")
                            break
                # TODO: remove
                if at_most > 0 and len(pdf_links) >= at_most:
                    break
                try:
                    logger.info('Clicking "next" button in the webpage...')
                    next_button = driver.find_element(By.CSS_SELECTOR, self.next_btn)
                    # sleep for a random short time to avoid being blocked
                    time.sleep(random.uniform(0.2, 0.5))
                    next_button.click()
                except NoSuchElementException:
                    logger.info("No more pages to scrape.")
                    break
        finally:
            driver.quit()
            logger.info("Chrome driver closed.")

        return pdf_links

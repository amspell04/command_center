from datetime import datetime

import requests
from bs4 import BeautifulSoup
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import letter

urls_to_scan = ["https://www.reuters.com/technology/", "https://techcrunch.com/"]


def fetch_news():
    for url in urls_to_scan:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(resp.text, "html.parser")
        titles = [a.text for a in soup.find_all("span", class_="titleline")][:15]

        found_news = "\n".join(f"- {title}" for title in titles)
    
    return found_news


def build_briefing(text_content, filename):
    doc = SimpleDocTemplate(filename, pagesize=letter)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'NewspaperTitle',
        parent=styles['Heading1'],
        fontSize=24,
        leading=28,
        spaceAfter=12
    )
    
    story = [
        Paragraph("AMELIA'S MORNING TECH DIGEST", title_style),
        Spacer(1, 12)
    ]
    
    for paragraph in text_content.split("\n\n"):
        story.append(Paragraph(paragraph.replace("\n", "<br/>"), styles['Normal']))
        story.append(Spacer(1, 10))
        
    doc.build(story)
    return filename


def generate_todays_briefing():
    todays_date = datetime.date
    briefing_name = "morning_digest" + todays_date

    todays_news = fetch_news()
    summarized_news = invoke_news_analysis(todays_news)
    briefing_path = create_briefing(summarized_news, briefing_name)

    subprocess.run(["lp", briefing_path])
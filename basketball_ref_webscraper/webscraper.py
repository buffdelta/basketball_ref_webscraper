import re
import datetime

from bs4 import BeautifulSoup, Comment
from ratelimit import limits, sleep_and_retry
from tenacity import retry, stop_never, wait_fixed, retry_if_exception_type

import requests

BASE_URL = 'https://www.basketball-reference.com'

@retry(
    stop=stop_never,
    wait=wait_fixed(3),
    retry=retry_if_exception_type((requests.exceptions.RequestException, requests.exceptions.ConnectionError)),
)
@sleep_and_retry
@limits(calls=1, period=3.00)
def make_request(request_url: str) -> str:
    """ Make a request to basketball-reference for the page. Limit to 20 request per minute
    (https://www.sports-reference.com/429.html), or one every three seconds. Retry if there is a
    connection error.

    Args:
        request_url (str): URL for basketball-reference.

    Returns:
        str: HTML text of page.

    """
    response = requests.get(request_url, timeout=3.0)
    return response.text


def get_boxscore(request_url: str) -> dict[str, str | float]:
    text = make_request(request_url)
    soup = BeautifulSoup(text, 'html.parser')

    teams = soup.find('div', {'class': 'scorebox'}).find_all('strong')
    data = {
        'match_date': datetime.datetime.strptime(request_url[47:55], '%Y%m%d'),
        'visit_team': teams[0].find('a').get('href').split('/')[2],
        'home_team': teams[1].find('a').get('href').split('/')[2],
        'is_playoff': 1 if soup.find('span', { 'data-label':'All Games in Series'}) is not None else 0
    }

    data['playoff_round'] = re.search(r'Game (\d)', soup.find('h1').text).group(1) if data['is_playoff'] == 1 else 0

    visit_stats = soup.find('table', id='box-' + data['visit_team'] + '-game-basic').find('tfoot').find_all('td', string=lambda text: text and text.strip())
    home_stats = soup.find('table', id='box-' + data['home_team'] + '-game-basic').find('tfoot').find_all('td', string=lambda text: text and text.strip())

    for v_cell, h_cell in zip(visit_stats, home_stats):
        data['visit_' + v_cell['data-stat']] = v_cell.text
        data['home_' + h_cell['data-stat']] = h_cell.text

    data['game_result'] = data['home_team'] if int(data['home_pts']) > int(data['visit_pts']) else data['visit_team']

    return data


def get_roster(team: str, year: int):
    text = make_request(f'{BASE_URL}/teams/{team}/{year}.html')
    soup = BeautifulSoup(text, 'html.parser')
    table_rows = soup.find('div', id='div_roster').find('tbody').find_all('tr')

    roster_data = []
    for row in table_rows:
        table_cells = row.find_all('td')
        data = {}
        for table_cell in table_cells:
            data_stat = table_cell['data-stat']
            match data_stat:
                case 'weight':
                    data['weight'] = int(table_cell.text)
                case 'player':
                    data['player'] = table_cell['csk']
                    url = table_cell.find('a').get('href')
                    data['url'] = url
                    data['playerid'] = url.split('/')[-1].replace('.html', '')
                case 'years_experience':
                    data[data_stat] = float(table_cell['csk'])
                case 'flag':
                    data[data_stat] = table_cell.find('span').text
                case 'height':
                    data[data_stat] = float(table_cell['csk'])
                case _:
                    data[data_stat] = table_cell.text
        roster_data.append(data)

    return roster_data


def get_injury_report(team: str, year: int):
    text = make_request(f'{BASE_URL}/teams/{team}/{year}.html')
    soup = BeautifulSoup(text, 'html.parser')
    container = soup.find('div', id='all_injuries')
    if not container:
        return None
    comment = container.find(string=lambda text: isinstance(text, Comment))
    if not comment:
        return None
    comment_soup = BeautifulSoup(comment, 'html.parser')
    injured_players = [th['csk'] for th in comment_soup.find('table').find_all('th', attrs={'csk': True})]
    return injured_players


def get_all_schedule(year: int) -> list[dict]:
    season_url = f'{BASE_URL}/leagues/NBA_{year}_games.html'
    text = make_request(season_url)

    schedule_data = _parse_matches_from_text(text)

    for month_url in _get_month_links(text)[1:]:
        month_text = make_request(month_url)
        schedule_data.extend(_parse_matches_from_text(month_text))

    return schedule_data


def get_team_schedule(team: str, year: int) -> list[dict]:
    season_url = f'{BASE_URL}/leagues/NBA_{year}_games.html'
    text = make_request(season_url)

    team_schedule = [m for m in _parse_matches_from_text(text) if team in (m['home_team'], m['visit_team'])]

    for month_url in _get_month_links(text)[1:]:
        month_text = make_request(month_url)
        month_matches = [m for m in _parse_matches_from_text(month_text) if team in (m['home_team'], m['visit_team'])]
        team_schedule.extend(month_matches)

    return team_schedule


def _get_month_links(text: str) -> list[str]:
    months = BeautifulSoup(text, 'html.parser').find('div', {'class': 'filter'}).find_all('a')
    return [BASE_URL + a.get('href') for a in months]


def _parse_matches_from_text(text: str) -> list[dict]:
    soup = BeautifulSoup(text, 'html.parser')
    matches = soup.find('tbody').find_all('tr')
    return [get_match_data(match) for match in matches if match.text.strip() != "Playoffs"]


def get_match_data(match):
    team_names = match.find('td', {'data-stat':'visitor_team_name'}).get('csk')
    visit_team = team_names[0:3]
    home_team = team_names[13:16]
    match_date = match.find('th', {'data-stat': 'date_game'}).get('csk')[0:8]
    box_score = match.find('td', {'data-stat': 'box_score_text'}).find('a')
    if box_score is not None:
        match_link = BASE_URL + box_score.get('href')
    else:
        match_link = BASE_URL + '/boxscores/' + match_date + home_team + '0.html'
    return { 'match_link':match_link, 'match_date':match_date, 'visit_team':visit_team, 'home_team':home_team }

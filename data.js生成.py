import json, requests
from functools import reduce

output_file = 'data.js'

unitTimeRange = {
    1: (7*60+50, 8*60+35),
    2: (8*60+40, 9*60+25),
    3: (9*60+45, 10*60+30),
    4: (10*60+35, 11*60+20),
    5: (11*60+25, 12*60+10),
    6: (14*60+0, 14*60+45),
    7: (14*60+50, 15*60+35),
    8: (15*60+55, 16*60+40),
    9: (16*60+45, 17*60+30),
    10: (17*60+35, 18*60+20),
    11: (19*60+30, 20*60+15),
    12: (20*60+20, 21*60+5),
    13: (21*60+10, 21*60+55),
}

urls = {
    'get_token': 'https://catalog.ustc.edu.cn/get_token',
    'semester_list': 'https://catalog.ustc.edu.cn/api/teach/semester/list?access_token={access_token}',
    'lesson_list': 'https://catalog.ustc.edu.cn/api/teach/lesson/list-for-teach/{semester_id}?access_token={access_token}',
}

# access_token = requests.get(urls['get_token']).json()['access_token']
access_token = ''
semester_list = requests.get(urls['semester_list'].format(access_token = access_token)).json()
print(semester_list)
# semester_new = reduce(lambda x, y: y if x['end'] < y['end'] else x, semester_list)
# semester_id = semester_new['id']
semester_id = 382
lesson_list = requests.get(urls['lesson_list'].format(access_token = access_token, semester_id = semester_id)).json()

for lesson in lesson_list:
    teachers = [teacher['cn'] for teacher in lesson['teacherAssignmentList']]
    lesson['teachers'] = teachers # 用于评课社区评分, 不应输出到 data.js
    if len(teachers) >= 3:
        teachers = teachers[:2] + ['...']
    lesson['teacher'] = ','.join(teachers)

def dealTime(info: str):
    result = 0
    if info is None:
        return result
    for x in info.split(';'):
        if x.strip() in ('', '#1'):
            continue
        x = str(x)
        pos = x.rfind('(')
        day = int(x[x.rfind(':', 0, pos)+2:pos]) - 1
        x = x[pos+1:-1]
        if '~' in x:
            units = []
            st0, ed0 = map(lambda x: int(x[:2]) * 60 + int(x[3:]), x.split('~'))
            for unit in unitTimeRange:
                st1, ed1 = unitTimeRange[unit]
                if max(st0, st1) < min(ed0, ed1):
                    units.append(unit)
        else:
            units = list(map(int, x.split(',')))
        if 1 in units or 2 in units:
            result |= 1 << (day * 6 + 0)
        if 3 in units or 4 in units or 5 in units:
            result |= 1 << (day * 6 + 1)
        if 6 in units or 7 in units:
            result |= 1 << (day * 6 + 2)
        if 8 in units:
            result |= 1 << (day * 6 + 3)
        if 9 in units or 10 in units:
            result |= 1 << (day * 6 + 4)
        if 11 in units or 12 in units or 13 in units:
            result |= 1 << (day * 6 + 5)
    return result

def dealWeek(info):
    if info is None:
        return 0
    result = 0
    for period in info.split('\n'):
        if '周 ' not in period:
            continue
        period = period.split('周 ')[0]
        for x in period.split(','):
            if '~' not in x and str(int(x)) == x:
                result |= 1 << int(x)
                continue
            special = ''
            if x.endswith('(单)'):
                special = 'Odd'
                x = x[:-3]
            if x.endswith('(双)'):
                special = 'Even'
                x = x[:-3]
            t = x.split('~')
            assert len(t) == 2, t
            if special == 'Odd':
                for week in range(int(t[0]), int(t[1]) + 1):
                    if week % 2 == 1:
                        result |= 1 << week
            elif special == 'Even':
                for week in range(int(t[0]), int(t[1]) + 1):
                    if week % 2 == 0:
                        result |= 1 << week
            else:
                for week in range(int(t[0]), int(t[1]) + 1):
                    result |= 1 << week
    result >>= 1 # 1~18 -> 0~17
    assert result <= 2**20, info
    return result

output = []
for course in lesson_list:
    time = dealTime(course['dateTimePlaceText'])
    sim_course = {
        'code': course['code'],
        'courseName': course['course']['cn'],
        'teacher': course['teacher'],
        'teachers': course['teachers'], # 用于评课社区评分, 不应输出到 data.js
        'weekType': dealWeek(course['dateTimePlacePersonText']['cn']),
        'timeType0': time & ((1 << 30) - 1), 
        'credit': course['credits']
    }
    if time >> 30:
        sim_course['timeType1'] = time >> 30
    if course['classType']['cn'].find('通识') != -1:
        sim_course['tongshi'] = 1
    if course['dateTimePlaceText'] is None:
        sim_course['placeDayTime'] = ''
    else:
        sim_course['placeDayTime'] = course['dateTimePlaceText'].replace(' ', '').replace('\n', '')
    for key in sim_course:
        if sim_course[key] is None:
            print(sim_course)
    output.append(sim_course)


##### 处理评课社区评分 #####
from icourse_spider import lesson_match
for lesson in output:
    icourseRating = lesson_match.get_icourseRating(lesson['courseName'], lesson['teachers'])
    if icourseRating != '暂无评分':
        lesson['icourseRating'] = icourseRating
    lesson.pop('teachers')
##### 完成评分处理 #####

output.sort(key=lambda x: x['code'])
final_data = json.dumps(output, ensure_ascii=False, separators=(',', ':'))
final_data = final_data.replace('"code"', 'code')
final_data = final_data.replace('"courseName"', 'courseName')
final_data = final_data.replace('"teacher"', 'teacher')
final_data = final_data.replace('"weekType"', 'weekType')
final_data = final_data.replace('"timeType0"', 'timeType0')
final_data = final_data.replace('"timeType1"', 'timeType1')
final_data = final_data.replace('"tongshi"', 'tongshi')
final_data = final_data.replace('"placeDayTime"', 'placeDayTime')
final_data = final_data.replace('"icourseRating"', 'icourseRating')
with open(output_file, 'w', encoding='utf-8') as f:
    f.write('var version="251208";var semester="2025年秋季学期";var allLesson=' + final_data + ';')
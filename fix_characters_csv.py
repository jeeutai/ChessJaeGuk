import csv

# 올바른 헤더 정의
headers = [
    'id', 'user_id', 'class', 'level', 'exp', 'hp', 'mp', 'strength', 
    'agility', 'intelligence', 'skill_points', 'gold', 'inventory', 
    'equipment', 'pet_id', 'quests_completed', 'wins', 'losses', 
    'achievement_points', 'guild_id', 'status_effects', 'title', 'color',
    'avatar', 'name', 'last_training'
]

# 기존 데이터 추출 (가능한 경우)
existing_data = []
try:
    with open('data/characters.csv.bak', 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader)  # 헤더 건너뛰기
        for row in reader:
            if len(row) > 0:
                # 데이터 추출 시도
                try:
                    # 첫 번째 필드가 배열 형태의 문자열인 경우
                    if row[0].startswith('['):
                        # 문자열에서 값 추출
                        values = row[0].strip('[]').replace("'", "").split(', ')
                        if len(values) >= 23:
                            char_data = {
                                'id': values[0],
                                'user_id': values[1],
                                'class': values[2],
                                'level': values[3],
                                'exp': values[4],
                                'hp': values[5],
                                'mp': values[6],
                                'strength': values[7],
                                'agility': values[8],
                                'intelligence': values[9],
                                'skill_points': values[10],
                                'gold': values[11],
                                'inventory': values[12],
                                'equipment': values[13],
                                'pet_id': values[14],
                                'quests_completed': values[15],
                                'wins': values[16],
                                'losses': values[17],
                                'achievement_points': values[18],
                                'guild_id': values[19],
                                'status_effects': values[20],
                                'title': values[21],
                                'color': values[22] if len(values) > 22 else '',
                                'avatar': '',
                                'name': '',
                                'last_training': ''
                            }
                            existing_data.append(char_data)
                    # 일반적인 형태의 행인 경우
                    elif len(row) >= 10:
                        char_data = {}
                        for i, field in enumerate(headers):
                            if i < len(row):
                                char_data[field] = row[i]
                            else:
                                char_data[field] = ''
                        existing_data.append(char_data)
                except Exception as e:
                    print(f"행 처리 중 오류 발생: {e}")
                    continue
except Exception as e:
    print(f"파일 읽기 오류: {e}")

# 새 파일 생성
with open('data/characters.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=headers)
    writer.writeheader()
    writer.writerows(existing_data)

print(f"characters.csv 파일이 재생성되었습니다. {len(existing_data)}개의 캐릭터 데이터가 복구되었습니다.")

import os
import csv
from datetime import datetime

# CSV 파일 경로
CSV_FILES = {
    'users': 'data/users.csv',
    'transactions': 'data/transactions.csv',
    'login_logs': 'data/login_logs.csv',
    'market_logs': 'data/market_logs.csv',
    'game_logs': 'data/game_logs.csv',
    'items': 'data/items.csv',
    'stocks': 'data/stocks.csv',
    'notices': 'data/notices.csv',
    'chat_messages': 'data/chat_messages.csv'
}

# 데이터 디렉토리 생성
os.makedirs('data', exist_ok=True)

# CSV 파일 초기화 함수
def init_csv_files():
    # users.csv
    if not os.path.exists(CSV_FILES['users']):
        with open(CSV_FILES['users'], 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['id', 'password', 'nickname', 'email', 'phone', 'birth_date', 'balance', 'is_admin', 'created_at'])
            # 관리자 계정 생성
            writer.writerow(['admin', 'admin123', '관리자', 'admin@chess.com', '01012345678', '990101', '9999999999', 'True', str(datetime.now())])

    # transactions.csv
    if not os.path.exists(CSV_FILES['transactions']):
        with open(CSV_FILES['transactions'], 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['id', 'sender_id', 'receiver_id', 'amount', 'type', 'timestamp'])

    # login_logs.csv
    if not os.path.exists(CSV_FILES['login_logs']):
        with open(CSV_FILES['login_logs'], 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['id', 'user_id', 'timestamp', 'ip', 'status'])

    # game_logs.csv
    if not os.path.exists(CSV_FILES['game_logs']):
        with open(CSV_FILES['game_logs'], 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['id', 'user_id', 'game_type', 'bet_amount', 'result', 'timestamp'])

    # market_logs.csv
    if not os.path.exists(CSV_FILES['market_logs']):
        with open(CSV_FILES['market_logs'], 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['id', 'user_id', 'item_id', 'quantity', 'price', 'timestamp'])

    # items.csv
    if not os.path.exists(CSV_FILES['items']):
        with open(CSV_FILES['items'], 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['id', 'name', 'effect', 'price', 'duration', 'max_uses'])
            writer.writerow(['1', '행운의 부적', '다음 게임에서 승리 확률 10% 증가', '1000', '1', '1'])
            writer.writerow(['2', '보너스 카드', '다음 거래에서 10% 추가 적립', '2000', '1', '1'])
            writer.writerow(['3', '프리미엄 뱃지', '프로필에 특별 뱃지 표시', '5000', '30', '1'])

    # stocks.csv
    if not os.path.exists(CSV_FILES['stocks']):
        with open(CSV_FILES['stocks'], 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['id', 'name', 'current_price', 'previous_price', 'change_percent', 'last_update'])
            writer.writerow(['1', '체스제국', '10000', '9500', '5.26', str(datetime.now())])
            writer.writerow(['2', '디지털뱅크', '5000', '5100', '-1.96', str(datetime.now())])
            writer.writerow(['3', '게임테크', '8000', '7800', '2.56', str(datetime.now())])

    # notices.csv
    if not os.path.exists(CSV_FILES['notices']):
        with open(CSV_FILES['notices'], 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['id', 'title', 'content', 'author_id', 'timestamp'])
            writer.writerow(['1', '체스제국 송금 시스템 오픈', '체스제국 송금 시스템이 오픈되었습니다. 많은 이용 바랍니다.', 'admin', str(datetime.now())])

    # chat_messages.csv
    if not os.path.exists(CSV_FILES['chat_messages']):
        with open(CSV_FILES['chat_messages'], 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['id', 'user_id', 'message', 'timestamp'])
            writer.writerow(['1', 'admin', '체스제국 채팅방에 오신 것을 환영합니다!', str(datetime.now())])

if __name__ == '__main__':
    init_csv_files()
    print("모든 CSV 파일이 초기화되었습니다.")

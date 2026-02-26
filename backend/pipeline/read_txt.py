import pandas as pd

# 다운로드한 파일명이 'region_code.txt'라고 가정
# sep='\t'는 탭으로 구분되어 있다는 뜻입니다. 
# 만약 쉼표라면 sep=','로 바꾸면 됩니다.
df_code = pd.read_csv('region_code.txt', sep='\t', encoding='cp949') 

# 우리가 필요한 건 '법정동코드'와 '법정동명'
# 코드 앞 5자리가 구 단위 코드이므로 이를 추출하는 전처리가 필요합니다.
df_code['region_5digit'] = df_code['법정동코드'].astype(str).str[:5]

print(df_code.head())
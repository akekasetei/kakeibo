from dotenv import load_dotenv  # ← これが必要！
import os
import openai
from dotenv import load_dotenv
load_dotenv()  # .env から環境変数を読み込み
openai.api_key = os.getenv("OPENAI_API_KEY")  # 環境変数からAPIキーを設定
import streamlit as st
import openai
import pandas as pd
import re
from io import StringIO
from datetime import datetime, timedelta

st.title("ざっくり家計簿アプリ")

user_input = st.text_area("ここに入力してください", height=200)

def extract_number(s):
    if pd.isnull(s):
        return None
    match = re.search(r'\d+', str(s).replace(",", "").replace("　", "").replace(" ", ""))
    return int(match.group()) if match else None

# ChatGPTで表生成
if st.button("要約＋表を生成") and user_input.strip():
    with st.spinner("ChatGPTが表を作成中..."):
        try:
            prompt = f"""
以下のテキストは1日の食事記録です。この中から次の5項目を含む表をMarkdown形式で作成してください：

- 日付（例：2025-05-28）
- 食事区分（朝食、昼食、夕食）
- 費用（日本円、メニューに基づく平均的価格で記入）
- カロリー（メニューに基づく平均的カロリーで記入）
- メニュー（自由記述）

表形式：
| 日付 | 食事区分 | メニュー | 費用 | カロリー |
|------|----------|----------|------|----------|

元のテキスト：
{user_input}
"""

            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "あなたは食事記録を表に変換する日本語アシスタントです。費用とカロリーは平均的な値を記入してください。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=700,
            )

            table_md = response.choices[0].message.content.strip()
            st.subheader("抽出された表（Markdown）")
            st.markdown(table_md)

            # Markdown → DataFrame
            table_lines = [line for line in table_md.splitlines() if '|' in line and not line.strip().startswith('|-')]
            if len(table_lines) >= 2:
                header = table_lines[0].strip('|').split('|')
                rows = [line.strip('|').split('|') for line in table_lines[1:]]
                df = pd.DataFrame(rows, columns=[col.strip() for col in header])
                st.subheader("抽出された表（DataFrame）")
                st.dataframe(df)

                # ✅ 正規化処理
                df["食事区分"] = (
                    df["食事区分"]
                    .astype(str)
                    .str.replace("　", "", regex=False)
                    .str.replace(" ", "", regex=False)
                    .str.strip()
                    .replace({"夜ごはん": "夕食", "晩ごはん": "夕食", "ディナー": "夕食"})
                )
                df["費用"] = df["費用"].apply(extract_number)
                df["カロリー"] = df["カロリー"].apply(extract_number)
                df["日付"] = pd.to_datetime(df["日付"], errors="coerce")

                # ✅ 保存処理
                save_path = "data/meal_records.csv"
                os.makedirs("data", exist_ok=True)
                if not os.path.exists(save_path):
                    df.to_csv(save_path, index=False)
                else:
                    df.to_csv(save_path, mode="a", index=False, header=False)

                st.success("データを保存しました。")
            else:
                st.warning("テーブルが正しく抽出されませんでした。")

        except Exception as e:
            st.error(f"エラーが発生しました: {e}")

# --------------------------------------------
# ✅ 1週間の夕食費用・カロリー合計
# --------------------------------------------

st.title("1週間の夕食費用・カロリー合計")

csv_path = "data/meal_records.csv"

if os.path.exists(csv_path):
    df_all = pd.read_csv(csv_path)

    df_all["日付"] = pd.to_datetime(df_all["日付"], errors="coerce")
    df_all["費用"] = pd.to_numeric(df_all["費用"], errors="coerce")
    df_all["カロリー"] = pd.to_numeric(df_all["カロリー"], errors="coerce")
    df_all["食事区分"] = (
        df_all["食事区分"]
        .astype(str)
        .str.replace("　", "", regex=False)
        .str.replace(" ", "", regex=False)
        .str.strip()
        .replace({"夜ごはん": "夕食", "晩ごはん": "夕食", "ディナー": "夕食"})
    )

    today = datetime.today().date()
    one_week_ago = today - timedelta(days=6)

    recent_dinner = df_all[
        (df_all["日付"].dt.date >= one_week_ago) &
        (df_all["日付"].dt.date <= today) &
        (df_all["食事区分"] == "夕食")
    ]

    total_cost = recent_dinner["費用"].sum()
    total_calories = recent_dinner["カロリー"].sum()

    st.subheader(f"{one_week_ago} 〜 {today} の集計")
    st.write(f"### 🍽️ 夕食の合計費用：{int(total_cost):,} 円")
    st.write(f"### 🔥 夕食の合計カロリー：{int(total_calories):,} kcal")

    if st.checkbox("データ確認（夕食のみ）"):
        st.dataframe(recent_dinner)
else:
    st.warning("記録データ（meal_records.csv）がまだ保存されていません。")


# データ削除セクション
st.subheader("⚠️ データをクリアする")
if st.button("すべての記録を削除する"):
    try:
        csv_path = "data/meal_records.csv"
        if os.path.exists(csv_path):
            os.remove(csv_path)
            st.success("保存されたデータをすべて削除しました。")
        else:
            st.info("削除するデータが存在しません。")
    except Exception as e:
        st.error(f"削除中にエラーが発生しました: {e}")


st.title("🛒 手入力による買い物記録")

# 保存先CSV
csv_path = "data/shopping_records.csv"
os.makedirs("data", exist_ok=True)

#手動入力
with st.form("shopping_form"):
    date = st.date_input("日付",datetime.today())
    price = st.number_input("金額（円）",min_value=0,step=10)

    # ✅ フォーム内に submit ボタンを配置
    submitted = st.form_submit_button("保存する")

if submitted:
    new_row = pd.DataFrame({
        "日付": [date],
        "金額": [price]
    })

# 既存CSVがあれば読み込んで追記、なければ新規保存
    if os.path.exists(csv_path):
        old_df = pd.read_csv(csv_path)
        df = pd.concat([old_df, new_row], ignore_index=True)
    else:
        df = new_row

    df.to_csv(csv_path, index=False)
    st.success("✅ 買い物記録を保存しました！")


# 表示
if os.path.exists(csv_path):
    df_show = pd.read_csv(csv_path)
    st.subheader("📊 保存された買い物記録")
    st.dataframe(df_show)

    st.write(f"💰 合計金額：{int(df_show['金額'].sum()):,} 円")
else:
    st.info("まだ買い物データは保存されていません。")





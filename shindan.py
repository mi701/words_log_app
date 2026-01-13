"""
Gemini API 生成対応モデル自動識別・生成診断ツール
- ListModels を唯一の情報源とする
- generateContent 対応モデルのみ抽出
- Flash / Pro 系を自動分類
- 各カテゴリで「最新らしきモデル」を自動選択
- 超短文生成で最終確認

2026 diagnostic edition
"""

import re
import sys

try:
    import google.generativeai as genai
    from google.api_core import exceptions
except ImportError:
    print("必要なパッケージがありません。以下を実行してください:")
    print("pip install google-generativeai google-api-core")
    sys.exit(1)


def normalize_name(name: str) -> str:
    return name.lower()


def extract_date_score(name: str) -> int:
    """
    モデル名に含まれる YYYYMM / YYYY-MM / YYYY をスコア化
    数値が大きいほど新しいとみなす
    """
    matches = re.findall(r"(20\d{2})(\d{2})?", name)
    if not matches:
        return 0

    year, month = matches[-1]
    score = int(year) * 100
    if month:
        score += int(month)
    return score


def classify_models(models):
    flash = []
    pro = []

    for m in models:
        name = normalize_name(m.name)

        if "generatecontent" not in [x.lower() for x in m.supported_generation_methods]:
            continue

        if "flash" in name:
            flash.append(m)
        elif any(k in name for k in ["pro", "thinking", "research"]):
            pro.append(m)

    return flash, pro


def select_latest(models):
    if not models:
        return None

    scored = []
    for m in models:
        score = extract_date_score(m.name)
        scored.append((score, m))

    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1]


def test_generation(model_name):
    print(f"\n--- {model_name} 生成テスト ---")
    model = genai.GenerativeModel(model_name)

    try:
        res = model.generate_content("ping")
        print(" ✅ 生成成功")
        print(f"    応答: {res.text}")
        return "OK"

    except exceptions.ResourceExhausted as e:
        print(" ⚠ クォータ制限")
        print(f"    詳細: {e}")
        return "QUOTA"

    except exceptions.InvalidArgument as e:
        print(" ❌ 無効なリクエスト")
        print(f"    内容: {e}")
        return "INVALID"

    except Exception as e:
        print(" ❌ その他エラー")
        print(f"    内容: {e}")
        return "ERROR"


def main():
    print("--- Gemini API 自動モデル識別・生成診断 ---\n")

    api_key = input("APIキーを入力してください（表示されません）: ").strip()
    if not api_key:
        print("APIキーが入力されていません。終了します。")
        return

    genai.configure(api_key=api_key)

    # Step 1: ListModels
    print("\n[Step 1] モデル一覧取得")
    try:
        models = list(genai.list_models())
        print(f" ✅ {len(models)} モデル取得")
    except Exception as e:
        print(f" ❌ ListModels 失敗: {e}")
        return

    # Step 2: generateContent 対応モデル抽出
    print("\n[Step 2] generateContent 対応モデル抽出")
    gc_models = [
        m for m in models
        if "generateContent" in m.supported_generation_methods
    ]
    print(f" ✅ generateContent 対応: {len(gc_models)} モデル")

    # Step 3: 分類
    flash_models, pro_models = classify_models(gc_models)
    print(f"\n[Step 3] 分類結果")
    print(f" Flash 系: {len(flash_models)}")
    print(f" Pro / Thinking 系: {len(pro_models)}")

    # Step 4: 最新モデル選定
    flash_latest = select_latest(flash_models)
    pro_latest = select_latest(pro_models)

    print("\n[Step 4] 最新モデル候補")
    if flash_latest:
        print(f" Flash: {flash_latest.name}")
    else:
        print(" Flash: 該当なし")

    if pro_latest:
        print(f" Pro: {pro_latest.name}")
    else:
        print(" Pro: 該当なし")

    # Step 5: 生成テスト
    print("\n[Step 5] 生成テスト")
    results = {}

    if flash_latest:
        results[flash_latest.name] = test_generation(flash_latest.name)

    if pro_latest:
        results[pro_latest.name] = test_generation(pro_latest.name)

    # サマリ
    print("\n--- 診断サマリ ---")
    for name, status in results.items():
        print(f"{name}: {status}")

    print("\n観測完了。")


if __name__ == "__main__":
    main()

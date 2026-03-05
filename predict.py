from flask import Flask, request, jsonify
from flask_cors import CORS
import pandas as pd
import numpy as np
import pickle
from sklearn.metrics.pairwise import euclidean_distances

app = Flask(__name__)
CORS(app)

# ──────── AVL Tree 클래스 정의 ────────
class AVLNode:
    def __init__(self, key, data):
        self.key = key
        self.data = data
        self.height = 1
        self.left = None
        self.right = None

class AVLTree:
    def __init__(self):
        self.root = None

    def _height(self, node):
        return node.height if node else 0

    def _fix_height(self, node):
        node.height = max(self._height(node.left), self._height(node.right)) + 1

    def _balance_factor(self, node):
        return self._height(node.left) - self._height(node.right)

    def _rotate_right(self, y):
        x = y.left
        y.left = x.right
        x.right = y
        self._fix_height(y)
        self._fix_height(x)
        return x

    def _rotate_left(self, x):
        y = x.right
        x.right = y.left
        y.left = x
        self._fix_height(x)
        self._fix_height(y)
        return y

    def _balance(self, node):
        self._fix_height(node)
        if self._balance_factor(node) == 2:
            if self._balance_factor(node.left) < 0:
                node.left = self._rotate_left(node.left)
            return self._rotate_right(node)
        if self._balance_factor(node) == -2:
            if self._balance_factor(node.right) > 0:
                node.right = self._rotate_right(node.right)
            return self._rotate_left(node)
        return node

    def _insert(self, node, key, data):
        if not node:
            return AVLNode(key, data)
        if key < node.key:
            node.left = self._insert(node.left, key, data)
        else:
            node.right = self._insert(node.right, key, data)
        return self._balance(node)

    def insert(self, key, data):
        self.root = self._insert(self.root, key, data)

    def inorder(self):
        result = []
        def _dfs(node):
            if not node:
                return
            _dfs(node.left)
            result.append((node.key, node.data))
            _dfs(node.right)
        _dfs(self.root)
        return result

# ──────── 모델 및 AVL 트리 로드 ────────
with open("ridge_poly_model.pkl", "rb") as f:
    pipeline = pickle.load(f)

df_full = pd.read_excel("ModelData.xlsx")[[ 
    '귀소일자', '지역명', '전체인력수합계',
    '습도', '온도', '최대풍속', 
    '현장소방서거리', '현장안전센터거리'
]].dropna()

feature_cols = ['습도', '온도', '최대풍속', '현장소방서거리', '현장안전센터거리']
tree = AVLTree()

for _, row in df_full.iterrows():
    x = pd.DataFrame([row[feature_cols].values], columns=feature_cols)
    pred = pipeline.predict(x)[0]
    data = {
        'features': x.values.flatten(),
        '귀소일자': row['귀소일자'],
        '지역명': row['지역명'],
        'actual': int(row['전체인력수합계'])
    }
    tree.insert(pred, data)

# ──────── 예측 API ────────
@app.route('/predict', methods=['POST'])
def predict():
    data = request.json
    try:
        required_keys = ["현장소방서거리", "현장안전센터거리", "최대풍속", "온도", "습도"]
        for key in required_keys:
            if key not in data:
                return jsonify({"error": f"'{key}' 값이 없습니다."}), 400

        # 입력값 포장
        input_df = pd.DataFrame([[ 
            float(data["습도"]), 
            float(data["온도"]),
            float(data["최대풍속"]),
            float(data["현장소방서거리"]),
            float(data["현장안전센터거리"])
        ]], columns=feature_cols)

        raw_pred = pipeline.predict(input_df)[0]
        pred = int(round(raw_pred))

        # AVL 기반 유사 사례 찾기
        nodes = tree.inorder()
        diffs = [(abs(key - raw_pred), case) for key, case in nodes]
        diffs.sort(key=lambda t: t[0])
        nearest = diffs[:2]

        actuals = [case['actual'] for _, case in nearest]
        lo, hi = min(actuals), max(actuals)

        # 결과 구성
        result_text = f"=== 모델 예측 결과 ===\n현 산불 상황 → 습도: {int(data['습도'])}%, 온도: {int(data['온도'])}°C, 순간 최대풍속: {int(data['최대풍속'])}m/s,\n               현장소방서거리: {data['현장소방서거리']}km, 현장안전센터거리: {data['현장안전센터거리']}km\n"

        for i, (_, case) in enumerate(nearest):
            result_text += f"\n유사 사례 #{i+1}\n- {case['귀소일자']}, {case['지역명']} 산불\n- 총 동원 인력수: {case['actual']}명\n"

        result_text += f"\n예상 동원 인력: {pred}명 (실제 투입 범위: {lo}~{hi}명)"

        return jsonify({"result": result_text})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(port=5001, debug=True)

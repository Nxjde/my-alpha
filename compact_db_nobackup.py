"""qanat.duckdb를 EXPORT/IMPORT로 압축한다. 디스크 공간이 부족해 백업 없이 진행.
실제 데이터는 몇 MB 수준이라 export 결과만 확인하고 넘어가면 안전하다."""

import duckdb
import shutil
import os

DB_PATH = "/home/ec2-user/my-alpha/data/qanat.duckdb"
EXPORT_DIR = "/home/ec2-user/my-alpha/data/_export_tmp"
OLD_RENAMED = DB_PATH + ".old"

print("1) 기존 DB에서 export 중...")
if os.path.exists(EXPORT_DIR):
    shutil.rmtree(EXPORT_DIR)
con = duckdb.connect(DB_PATH)
con.execute(f"EXPORT DATABASE '{EXPORT_DIR}' (FORMAT PARQUET)")
con.close()

export_size = sum(os.path.getsize(os.path.join(dp, f))
                   for dp, _, fnames in os.walk(EXPORT_DIR) for f in fnames)
print(f"   export 완료, 크기: {export_size / 1e6:.2f} MB")
if export_size < 1000:
    raise RuntimeError("export 결과가 비정상적으로 작음 -- 중단")

print("2) 기존 파일 이름 변경 (삭제 아님, 문제 생기면 복구 가능)...")
os.rename(DB_PATH, OLD_RENAMED)

print("3) 새 DB 파일 생성 후 import 중...")
con2 = duckdb.connect(DB_PATH)
con2.execute(f"IMPORT DATABASE '{EXPORT_DIR}'")
con2.close()

old_size = os.path.getsize(OLD_RENAMED)
new_size = os.path.getsize(DB_PATH)
print(f"4) 완료: {old_size / 1e9:.2f} GB -> {new_size / 1e6:.2f} MB")
print(f"\n문제 없으면 지우세요: rm -rf {OLD_RENAMED} {EXPORT_DIR}")
print(f"문제 있으면 복구: mv {OLD_RENAMED} {DB_PATH}")

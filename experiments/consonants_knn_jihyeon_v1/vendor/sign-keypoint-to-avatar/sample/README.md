## sample 폴더

`sample/`에는 WORD2153 테스트에 사용한 중간 데이터와
VRM 구조 정보 JSON 파일을 저장합니다.

- `WORD2153_3d_approx.json`
  - WORD2153의 5개 시점 2D keypoint를 이용해 근사 복원한 3D 관절 데이터
  - 몸, 손, 얼굴 좌표가 프레임별로 저장되어 있음

- `vroid_rig_info.json`
  - `export_vroid_rig_info.py` 실행 결과
  - VRM의 Bone 이름, 부모 관계, 위치, 길이, 기본 행렬 정보

- `vroid_face_info.json`
  - `export_vroid_face_info.py` 실행 결과
  - VRM Face Mesh의 Shape Key 목록과 기본 값 정보


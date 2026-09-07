# Babylon.js KSL keypoint retargeting test

OpenPose 2D 키포인트를 Babylon.js의 GLB 아바타 본과 얼굴 morph target에 적용해 보는 실험 코드입니다.

현재 샘플 설정은 `WORD1202(추억)`, 정면(`F`), 57프레임을 기준으로 합니다. 팀원 테스트용 키포인트 JSON 57개는 포함하며, 원본 영상과 GLB는 저장소 정책상 커밋하지 않습니다.

## 로컬 파일 배치

키포인트 JSON은 저장소에 포함되어 있습니다. 아래 구조처럼 영상과 GLB만 직접 놓아 주세요.

```text
babylon-keypoint-test/
├─ models/
│  └─ ksl_avatar.glb
└─ sample/
   ├─ word1202_memory.mp4
   └─ keypoints/
      ├─ NIA_SL_WORD1202_SYN03_F_000000000000_keypoints.json
      ├─ ...
      └─ NIA_SL_WORD1202_SYN03_F_000000000056_keypoints.json
```

원본 테스트 환경의 데이터 경로:

- 영상: `D:\매핑용( 단어 생성 비디오, 단어)\map_syn\datasets\syn_video\WORD\03\NIA_SL_WORD1202_SYN03_F.mp4`
- 키포인트: `D:\수어 영상\2.Validation\[라벨]02_syn_word_keypoint\WORD\keypoint\03\NIA_SL_WORD1202_SYN03_F\`

## 실행

Windows에서 `start-demo.cmd`를 실행한 뒤 `http://127.0.0.1:8080/`에 접속합니다. 검은 서버 창은 실행 중 계속 열어 둡니다.

## 현재 한계

- 입력이 2D이므로 팔의 깊이와 손목 비틀림은 정확히 복원할 수 없습니다.
- 모델마다 본의 로컬 축이 달라 추가 캘리브레이션이 필요합니다.
- 손가락 굽힘과 눈 감기/입 벌림 morph는 휴리스틱 매핑입니다.
- 현재 코드는 동작 가능성 확인을 위한 프로토타입이며 학습/서비스용 파이프라인이 아닙니다.

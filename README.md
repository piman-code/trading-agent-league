# Trading Agent League (Obsidian Plugin)

`trading-agent-league`를 Obsidian에서 라운드 기록/순위표 생성에 쓰는 플러그인입니다.

## BRAT 설치
1. Obsidian에서 **BRAT** 플러그인 설치/활성화
2. BRAT → **Add a beta plugin**
3. 아래 저장소 URL 입력:
   - `https://github.com/piman-code/trading-agent-league`
4. 설치 후 커맨드 팔레트에서 아래 명령 실행

## 제공 명령어
- `TAL: 라운드 노트 생성`
  - 리그명/라운드/참가자 입력 모달
  - 라운드 템플릿 노트 자동 생성
- `TAL: Results에서 순위표 생성`
  - `## Results`의 `- 이름: 수익률%` 형식 파싱
  - 수익률 기준 순위표 생성

## Results 형식 예시
```md
## Results
- Alpha: 3.12%
- Beta: -0.42%
- Gamma: 1.07%
```

## BRAT 호환 파일
- `manifest.json`
- `main.js`
- `versions.json`

위 3개 파일을 저장소 루트에 두어 BRAT에서 바로 인식되도록 구성했습니다.

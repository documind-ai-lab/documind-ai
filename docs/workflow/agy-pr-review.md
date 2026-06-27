# Antigravity PR 리뷰

CodeRabbit을 필수 리뷰 도구로 사용하지 않고, Antigravity CLI(`agy`)를 PR 일반 댓글 리뷰어로 사용합니다.

## 사전 조건

- `gh` CLI 인증이 완료되어 있어야 합니다.
- `agy` CLI가 PATH에 있어야 합니다.
- PR diff가 외부 AI 서비스인 Antigravity로 전달된다는 점을 이해하고 실행해야 합니다.

## 사용법

리뷰 결과를 터미널에만 출력합니다.

```bash
scripts/agy-pr-review 12
```

리뷰 결과를 PR 댓글로 생성하거나 기존 Antigravity 리뷰 댓글을 갱신합니다.

```bash
scripts/agy-pr-review 12 --post
```

다른 저장소를 명시하려면 `--repo`를 사용합니다.

```bash
scripts/agy-pr-review 12 --repo documind-ai-lab/documind-client --post
```

## 운영 기준

- `agy`는 코드를 수정하지 않고 리뷰 코멘트만 작성하도록 프롬프트합니다.
- 댓글에는 `<!-- agy-pr-review -->` 마커를 넣어 같은 PR에서 재실행할 때 기존 댓글을 갱신합니다.
- GitHub inline review가 아니라 PR Conversation의 일반 댓글로 남깁니다.
- 머지 전에는 `agy` 리뷰 결과, 로컬 검증 결과, 남은 리스크를 PR 댓글이나 본문에 남깁니다.

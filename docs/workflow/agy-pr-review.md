# Antigravity PR 리뷰

Antigravity CLI(`agy`)를 PR 일반 댓글 리뷰어로 사용합니다.

## 사전 조건

- `gh` CLI 인증이 완료되어 있어야 합니다.
- `agy` CLI가 PATH에 있어야 합니다.
- Python 3.9 이상을 권장합니다.
- PR diff가 외부 AI 서비스인 Antigravity로 전달된다는 점을 이해하고 실행해야 합니다.

## 기본 모델

기본 리뷰 모델은 `Gemini 3.1 Pro (High)`입니다.

스크립트는 로컬 `agy` CLI 설정에 의존하지 않고 기본 실행 시에도 `--model "Gemini 3.1 Pro (High)"`를 명시해서 실행합니다.

## 사용법

리뷰 결과를 터미널에만 출력합니다.

```bash
scripts/agy-pr-review 12
```

리뷰 결과를 PR 댓글로 생성하거나 기존 Antigravity 리뷰 댓글을 갱신합니다.

```bash
scripts/agy-pr-review 12 --post
```

다른 모델을 사용해야 할 때는 `--model`로 일시적으로 덮어씁니다.

```bash
scripts/agy-pr-review 12 --post --model "Gemini 3.5 Flash (High)"
```

다른 저장소를 명시하려면 `--repo`를 사용합니다.

```bash
scripts/agy-pr-review 12 --repo documind-ai-lab/documind-client --post
```

큰 PR은 기본적으로 300000 bytes를 초과하면 중단합니다. 필요하면 값을 조정할 수 있습니다.

```bash
scripts/agy-pr-review 12 --post --max-diff-bytes 500000
```

## 템플릿 파일

리뷰 문구는 Python 코드 안에 직접 작성하지 않고 템플릿 파일로 관리합니다.

- `templates/agy-review-prompt.md`: Antigravity에 전달하는 리뷰 지시문
- `templates/agy-review-comment.md`: GitHub PR Conversation에 남기는 댓글 형식

템플릿별 치환값은 다음과 같습니다.

- `templates/agy-review-prompt.md`: `{{repo}}`, `{{pr_number}}`, `{{diff}}`
- `templates/agy-review-comment.md`: `{{marker}}`, `{{repo}}`, `{{pr_number}}`, `{{generated_at}}`, `{{command}}`, `{{model}}`, `{{review}}`

알 수 없는 치환값은 오타 방지를 위해 오류로 처리합니다. 템플릿 본문에 중괄호 토큰을 문자 그대로 남겨야 하면 `\{{name}}`처럼 앞에 역슬래시를 붙입니다.

## 운영 기준

- 현재 1차 버전은 로컬 개발자 터미널 실행을 기준으로 합니다. CI 자동 실행은 별도 검토 후 확장합니다.

- `agy`는 코드를 수정하지 않고 리뷰 코멘트만 작성하도록 템플릿으로 프롬프트합니다.
- 기본 모델은 `Gemini 3.1 Pro (High)`이며, 특수한 상황에서만 `--model`로 변경합니다.
- 댓글에는 `<!-- agy-pr-review -->` 마커를 넣어 같은 PR에서 재실행할 때 기존 댓글을 갱신합니다.
- 댓글 조회는 GitHub API pagination 결과를 모아 기존 Antigravity 리뷰 댓글을 찾습니다.
- GitHub inline review가 아니라 PR Conversation의 일반 댓글로 남깁니다.
- 머지 전에는 `agy` 리뷰 결과, 로컬 검증 결과, 남은 리스크를 PR 댓글이나 본문에 남깁니다.

## 구현 메모

- PR diff는 `agy --print`의 stdin으로 전달해 큰 diff에서 명령 인자 길이 제한에 걸릴 가능성을 줄입니다.
- 스크립트는 `agy --print --print-timeout <값> --model "Gemini 3.1 Pro (High)"` 형태로 기본 모델을 명시합니다.
- 초대형 PR diff는 기본 300000 bytes에서 중단해 토큰 한도와 비용 리스크를 줄입니다.
- PR diff는 `templates/agy-review-prompt.md` 안에서 `<pr_diff>` 태그로 감싸 모델 지시문과 구분합니다.
- GitHub 댓글 길이 제한에 가까워지면 줄 단위로 UTF-8 바이트를 누적해 리뷰 결과를 일부 생략하고 작은 PR 단위로 나누도록 안내합니다.
- 댓글을 자를 때 닫는 백틱 공간을 먼저 확보한 뒤 줄 시작의 fenced code block 개수를 기준으로 닫는 백틱을 추가해 렌더링 깨짐을 줄입니다.
- PR 번호와 저장소명은 실행 전에 간단히 검증합니다.
- 템플릿 파일은 현재 실행 위치가 아니라 `scripts/agy-pr-review` 파일 위치를 기준으로 찾습니다.
- 기존 Antigravity 리뷰 댓글은 현재 GitHub 사용자와 `<!-- agy-pr-review -->` 시작 마커가 모두 일치할 때만 갱신합니다.

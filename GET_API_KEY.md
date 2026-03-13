# Как получить Dashscope API ключ

## Шаг 1: Зарегистрируйтесь на Alibaba Cloud

1. Перейдите на https://www.alibabacloud.com/
2. Нажмите "Sign Up" или "Free Account"
3. Заполните регистрационную форму
4. Подтвердите email и телефон

## Шаг 2: Активируйте Dashscope

1. Войдите в консоль: https://dashscope.console.aliyun.com/
2. Примите условия обслуживания
3. Активируйте сервис (может потребоваться верификация)

## Шаг 3: Создайте API ключ

1. Перейдите в **API Key Management**: https://dashscope.console.aliyun.com/apiKey
2. Нажмите **"Create New API Key"**
3. Скопируйте ключ (начинается с `sk-`)

⚠️ **Важно:** Ключ показывается только один раз! Сохраните его в безопасном месте.

## Шаг 4: Настройте агент

1. Откройте `.env.agent.secret` в проекте
2. Замените значение `LLM_API_KEY` на ваш ключ:

```env
LLM_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
LLM_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen3-coder-plus
```

## Шаг 5: Проверьте работу

```bash
cd /path/to/se-toolkit-lab-6
uv run agent.py "What is REST?"
```

Ожидаемый вывод:
```json
{"answer": "REST (Representational State Transfer)...", "tool_calls": []}
```

## Бесплатный лимит

Новые аккаунты получают бесплатные токены для тестирования. Проверьте актуальные лимиты в консоли Dashscope.

## Troubleshooting

**Ошибка 401 (Invalid API Key):**
- Убедитесь, что ключ начинается с `sk-`
- Проверьте, что ключ активирован в консоли
- Убедитесь, что нет лишних пробелов в `.env.agent.secret`

**Ошибка 404:**
- Проверьте правильность `LLM_API_BASE`
- Убедитесь, что модель `qwen3-coder-plus` доступна в вашем регионе

**Ошибка 429 (Rate Limit):**
- Вы превысили лимит запросов
- Подождите или увеличьте лимит в консоли

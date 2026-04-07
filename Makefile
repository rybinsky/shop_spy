# ShopSpy Makefile

.PHONY: help run dev install clean pack-extension db-stats db-clean check-deploy

# Дефолтная цель
help:
	@echo "🔍 ShopSpy — доступные команды:"
	@echo ""
	@echo "  make install          - Установить зависимости"
	@echo "  make run              - Запустить сервер (production)"
	@echo "  make dev              - Запустить сервер (development с автоперезагрузкой)"
	@echo ""
	@echo "  make pack-extension   - Собрать расширение (dist/shopspy.zip + .crx)"
	@echo ""
	@echo "  make clean            - Очистить временные файлы"
	@echo "  make db-stats         - Показать статистику БД"
	@echo "  make db-clean         - Очистить старые записи"
	@echo "  make check-deploy     - Проверка готовности к деплою"
	@echo ""

# ============================================
# Сервер
# ============================================

# Установка зависимостей
install:
	pip install -r requirements.txt

# Запуск сервера (production)
run:
	python -m backend.main

# Запуск сервера (development)
dev:
	ENVIRONMENT=development uvicorn backend.main:app --reload --port 8000

# ============================================
# Расширение
# ============================================

# Собрать расширение: dist/shopspy.zip + dist/shopspy.crx
pack-extension:
	python pack_crx.py

# ============================================
# Очистка
# ============================================

clean:
	@echo "🧹 Очистка..."
	@rm -rf dist/
	@rm -rf __pycache__/
	@rm -rf backend/__pycache__/
	@rm -rf backend/*/__pycache__/
	@rm -rf .pytest_cache/
	@rm -rf .mypy_cache/
	@rm -f *.pyc
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ Готово!"

# ============================================
# База данных
# ============================================

db-stats:
	@sqlite3 data/shopspy.db "SELECT 'Пользователи:', COUNT(*) FROM telegram_users WHERE is_active=1;"
	@sqlite3 data/shopspy.db "SELECT 'Отслеживания:', COUNT(*) FROM price_alerts WHERE is_active=1;"
	@sqlite3 data/shopspy.db "SELECT 'Товары:', COUNT(DISTINCT platform || product_id) FROM prices;"
	@sqlite3 data/shopspy.db "SELECT 'Записи цен:', COUNT(*) FROM prices;"

db-clean:
	@echo "🗑️  Удаление записей старше 365 дней..."
	@sqlite3 data/shopspy.db "DELETE FROM prices WHERE recorded_at < datetime('now', '-365 days');"
	@sqlite3 data/shopspy.db "VACUUM;"
	@echo "✅ Готово!"

# ============================================
# Деплой
# ============================================

check-deploy:
	@echo "🔍 Проверка готовности к деплою..."
	@echo ""
	@echo "── Файлы ──"
	@test -f requirements.txt   && echo "  ✅ requirements.txt"   || echo "  ❌ requirements.txt"
	@test -f Dockerfile         && echo "  ✅ Dockerfile"         || echo "  ❌ Dockerfile"
	@test -f backend/main.py    && echo "  ✅ backend/main.py"    || echo "  ❌ backend/main.py"
	@test -f backend/config.py  && echo "  ✅ backend/config.py"  || echo "  ❌ backend/config.py"
	@test -d extension          && echo "  ✅ extension/"         || echo "  ❌ extension/"
	@test -f extension/config.js && echo "  ✅ extension/config.js" || echo "  ❌ extension/config.js (API_BASE!)"
	@test -f templates/index.html && echo "  ✅ templates/index.html" || echo "  ⚠️  templates/index.html (optional)"
	@test -f templates/admin.html && echo "  ✅ templates/admin.html" || echo "  ⚠️  templates/admin.html (optional)"
	@echo ""
	@echo "── Переменные окружения для Render.com ──"
	@echo "  ENVIRONMENT=production          (обязательно)"
	@echo "  TELEGRAM_BOT_TOKEN=...          (для уведомлений)"
	@echo "  GEMINI_API_KEY=...              (для AI-анализа отзывов)"
	@echo "  ANTHROPIC_API_KEY=...           (альтернатива Gemini)"
	@echo ""
	@echo "  PORT задаётся Render автоматически."
	@echo ""
	@echo "── Расширение ──"
	@echo "  Убедитесь, что API_BASE в extension/config.js"
	@echo "  указывает на ваш Render URL."

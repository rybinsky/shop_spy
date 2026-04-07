# ShopSpy Makefile
# Быстрые команды для разработки и сборки

.PHONY: help run dev install clean build-extension pack-extension test crawl db-stats db-clean check-deploy

# Дефолтная цель
help:
	@echo "🔍 ShopSpy - доступные команды:"
	@echo ""
	@echo "  make install          - Установить зависимости"
	@echo "  make run              - Запустить сервер (production)"
	@echo "  make dev              - Запустить сервер (development с автоперезагрузкой)"
	@echo "  make crawl            - Запустить краулер вручную"
	@echo ""
	@echo "  make build-extension  - Собрать расширение в dist/extension/"
	@echo "  make pack-extension   - Создать ZIP-архив расширения"
	@echo ""
	@echo "  make clean            - Очистить временные файлы"
	@echo "  make db-stats         - Показать статистику БД"
	@echo "  make db-clean         - Очистить старые записи"
	@echo "  make check-deploy     - Проверка готовности к деплою"
	@echo ""

# Установка зависимостей
install:
	pip install -r requirements.txt

# Запуск сервера (production)
run:
	python -m backend.main

# Запуск сервера (development)
dev:
	ENVIRONMENT=development uvicorn backend.main:app --reload --port 8000

# Запуск краулера вручную
crawl:
	curl -X POST http://localhost:8000/api/crawl

# ============================================
# Расширение
# ============================================

# Сборка расширения в dist/
build-extension:
	@echo "📦 Сборка расширения..."
	@rm -rf dist/extension
	@mkdir -p dist/extension
	@cp -r extension/* dist/extension/
	@echo "✅ Расширение собрано в dist/extension/"
	@echo "   Установите в Chrome: chrome://extensions/ → Загрузить распакованное"

# Создание ZIP-архива расширения
pack-extension: build-extension
	@echo "🗜️  Создание ZIP-архива..."
	@cd dist && rm -f shopspy-extension.zip
	@cd dist/extension && zip -r ../shopspy-extension.zip .
	@echo "✅ Архив создан: dist/shopspy-extension.zip"
	@ls -lh dist/shopspy-extension.zip

# ============================================
# Очистка
# ============================================

# Очистить временные файлы
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

# Показать статистику БД
db-stats:
	@sqlite3 data/shopspy.db "SELECT 'Пользователи:', COUNT(*) FROM telegram_users WHERE is_active=1;"
	@sqlite3 data/shopspy.db "SELECT 'Отслеживания:', COUNT(*) FROM price_alerts WHERE is_active=1;"
	@sqlite3 data/shopspy.db "SELECT 'Товары:', COUNT(DISTINCT platform || product_id) FROM prices;"
	@sqlite3 data/shopspy.db "SELECT 'Записи цен:', COUNT(*) FROM prices;"

# Очистить старые записи (старше 365 дней)
db-clean:
	@echo "🗑️  Удаление записей старше 365 дней..."
	@sqlite3 data/shopspy.db "DELETE FROM prices WHERE recorded_at < datetime('now', '-365 days');"
	@sqlite3 data/shopspy.db "VACUUM;"
	@echo "✅ Готово!"

# ============================================
# Деплой
# ============================================

# Проверка готовности к деплою
check-deploy:
	@echo "🔍 Проверка готовности к деплою..."
	@test -f requirements.txt && echo "✅ requirements.txt" || echo "❌ requirements.txt не найден"
	@test -f backend/main.py && echo "✅ backend/main.py" || echo "❌ backend/main.py не найден"
	@test -d extension && echo "✅ extension/" || echo "❌ extension/ не найден"
	@test -f templates/dashboard.html && echo "✅ templates/dashboard.html" || echo "❌ dashboard.html не найден"
	@test -f templates/admin.html && echo "✅ templates/admin.html" || echo "❌ admin.html не найден"
	@echo ""
	@echo "📋 Переменные окружения для Render:"
	@echo "   TELEGRAM_BOT_TOKEN=ваш_токен"
	@echo "   GEMINI_API_KEY=ваш_ключ"
	@echo "   ENVIRONMENT=production"

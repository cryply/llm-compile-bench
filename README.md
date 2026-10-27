# bench — компилируемость кода у локальных моделей

## Установка на Spark
    pip install pyyaml pytest --break-system-packages
    sudo apt-get install -y g++ golang-go            # rust через rustup, node — nvm/apt
    cd bench/ts && npm install && cd ..
    ollama cp hf.co/vcruz305/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-GGUF:IQ4_NL nemotron35

## Запуск
    ./run.py                        # всё (переключает модели сам, ~1–2 часа)
    ./run.py -m qwen38 nemotron35   # только эти
    ./run.py -p rust_iso8601 -m qwen38 --no-switch   # быстрая проверка одного промпта

Результат: results/results_<дата>.csv + results/<model>/<prompt>.md (ответ) и .log (вывод компилятора).
summary.py печатает сводку: compile N/6, tests N/6, среднее время, tok/s.

## Добавить промпт
prompts/<name>.yaml: lang (rust|cpp|python|go|typescript|react), prompt, files.test.
Промпт должен жёстко задавать сигнатуру — тесты пишутся под неё.

## Что меряется
- compile: код из первого блока ```lang компилируется (cargo build / g++ / py_compile / go vet / tsc)
- tests: проходят заранее написанные тесты
- wall_s, tok/s, reasoning_chars — цена ответа

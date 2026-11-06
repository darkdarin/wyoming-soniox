#!/usr/bin/with-contenv bashio
# shellcheck shell=bash
if ! bashio::config.has_value 'api_key'; then
    bashio::exit.nok "Set the Soniox API key in the app configuration (https://console.soniox.com)"
fi

export SONIOX_API_KEY="$(bashio::config 'api_key')"
flags=()
# List options may contain spaces: read them one item per line.
while IFS= read -r term; do
    [ -n "${term}" ] && flags+=(--context-term "${term}")
done < <(jq -r '.context_terms[]' /data/options.json)
while IFS= read -r word; do
    [ -n "${word}" ] && flags+=(--wake-word "${word}")
done < <(jq -r '.wake_words[]' /data/options.json)
if bashio::config.has_value 'context_text'; then
    flags+=(--context-text "$(bashio::config 'context_text')")
fi
if bashio::config.has_value 'tts_voice'; then
    flags+=(--tts-voice "$(bashio::config 'tts_voice')")
fi
if bashio::config.false 'language_hints_strict'; then
    flags+=(--no-language-hints-strict)
fi
if bashio::config.true 'debug_logging'; then
    flags+=(--debug)
fi

python3 -m wyoming_soniox \
    --uri 'tcp://0.0.0.0:10300' \
    --language "$(bashio::config 'language')" \
    --model "$(bashio::config 'model')" \
    --endpoint-latency-adjustment-level "$(bashio::config 'endpoint_latency_adjustment_level')" \
    --endpoint-sensitivity "$(bashio::config 'endpoint_sensitivity')" \
    --max-endpoint-delay-ms "$(bashio::config 'max_endpoint_delay_ms')" \
    --max-utterance-s "$(bashio::config 'max_utterance_s')" \
    --tts-language "$(bashio::config 'tts_language')" \
    --tts-speed "$(bashio::config 'tts_speed')" \
    "${flags[@]}" &
server=$!
trap 'kill -TERM "${server}"' TERM INT

# Announce the server to Home Assistant once it accepts connections.
until (echo > /dev/tcp/localhost/10300) 2> /dev/null; do
    kill -0 "${server}" 2> /dev/null || break
    sleep 0.5
done
if kill -0 "${server}" 2> /dev/null; then
    if bashio::discovery "wyoming" "$(bashio::var.json uri "tcp://$(hostname):10300")" > /dev/null; then
        bashio::log.info "Sent discovery information to Home Assistant"
    else
        bashio::log.error "Discovery message to Home Assistant failed"
    fi
fi
wait "${server}"

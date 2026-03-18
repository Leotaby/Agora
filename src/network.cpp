#include "network.h"
#include <curl/curl.h>
#include <nlohmann/json.hpp>
#include <cmath>
#include <algorithm>
#include <iostream>

using json = nlohmann::json;

// ── curl helpers ─────────────────────────────────────────────────

static size_t write_cb(void* ptr, size_t size, size_t nmemb, std::string* data) {
    data->append(static_cast<char*>(ptr), size * nmemb);
    return size * nmemb;
}

static std::string http_get(const std::string& url) {
    CURL* curl = curl_easy_init();
    if (!curl) return "";
    std::string body;
    curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_cb);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &body);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, 10L);
    curl_easy_setopt(curl, CURLOPT_CONNECTTIMEOUT, 5L);
    CURLcode res = curl_easy_perform(curl);
    curl_easy_cleanup(curl);
    if (res != CURLE_OK) return "";
    return body;
}

// ── layout ───────────────────────────────────────────────────────

static void compute_layout(SimulationData& sim) {
    if (sim.nodes.empty()) return;

    // Find max assets for radius scaling
    float max_assets = 0;
    for (auto& n : sim.nodes)
        max_assets = std::max(max_assets, n.total_assets);

    const float circle_r = 6.0f;

    // Separate ECB from commercial banks
    int ecb_idx = -1;
    std::vector<int> commercial;
    for (int i = 0; i < (int)sim.nodes.size(); i++) {
        if (sim.nodes[i].type == "central_bank")
            ecb_idx = i;
        else
            commercial.push_back(i);
    }

    // Sort commercial banks by total_assets descending for prominent placement
    std::sort(commercial.begin(), commercial.end(), [&](int a, int b) {
        return sim.nodes[a].total_assets > sim.nodes[b].total_assets;
    });

    // Place commercial banks in a circle in the XZ plane
    int n = (int)commercial.size();
    for (int i = 0; i < n; i++) {
        float angle = (float)i * 2.0f * M_PI / (float)n - M_PI / 2.0f;
        auto& node = sim.nodes[commercial[i]];
        node.position = glm::vec3(
            circle_r * cosf(angle),
            0.0f,
            circle_r * sinf(angle)
        );
        node.radius = 0.2f + 0.6f * sqrtf(node.total_assets / max_assets);
    }

    // ECB elevated at top center
    if (ecb_idx >= 0) {
        sim.nodes[ecb_idx].position = glm::vec3(0.0f, 3.5f, 0.0f);
        sim.nodes[ecb_idx].radius = 0.5f;
    }

    // Build index
    sim.node_index.clear();
    for (int i = 0; i < (int)sim.nodes.size(); i++)
        sim.node_index[sim.nodes[i].id] = i;
}

// ── JSON parsing ─────────────────────────────────────────────────

static BankNode parse_bank_state(const json& j) {
    BankNode b;
    b.id = j.value("bank_id", j.value("id", ""));
    b.name = j.value("short_name", j.value("name", b.id));
    b.type = j.value("type", "");
    b.country = j.value("country", "");
    b.status = j.value("status", "normal");
    b.total_assets = j.value("total_assets_eur_bn", 0.0f);
    b.cet1_ratio_pct = j.value("cet1_ratio_pct", 0.0f);
    b.lcr_pct = j.value("lcr_pct", 0.0f);
    b.credit_spread_bps = j.value("credit_spread_bps", 0.0f);
    return b;
}

SimulationData fetch_simulation(const std::string& url) {
    SimulationData sim;

    std::cout << "Connecting to " << url << " ..." << std::endl;
    std::string body = http_get(url);
    if (body.empty()) {
        sim.error = "Could not connect to " + url;
        std::cerr << sim.error << std::endl;
        std::cerr << "Start the backend: cd backend && uv run python run.py" << std::endl;
        return sim;
    }

    json data;
    try {
        data = json::parse(body);
    } catch (const json::exception& e) {
        sim.error = std::string("JSON parse error: ") + e.what();
        std::cerr << sim.error << std::endl;
        return sim;
    }

    // Parse network nodes
    if (data.contains("network") && data["network"].contains("nodes")) {
        for (auto& jn : data["network"]["nodes"]) {
            BankNode node;
            node.id = jn.value("id", "");
            node.name = jn.value("name", node.id);
            node.type = jn.value("type", "");
            node.country = jn.value("country", "");
            node.status = jn.value("status", "normal");
            node.total_assets = jn.value("total_assets_eur_bn", 0.0f);
            node.cet1_ratio_pct = jn.value("cet1_ratio_pct", 0.0f);
            node.lcr_pct = jn.value("lcr_pct", 0.0f);
            node.credit_spread_bps = jn.value("credit_spread_bps", 0.0f);
            sim.nodes.push_back(node);
        }
    }

    // Parse network edges
    if (data.contains("network") && data["network"].contains("edges")) {
        for (auto& je : data["network"]["edges"]) {
            NetworkEdge edge;
            edge.source = je.value("source", "");
            edge.target = je.value("target", "");
            edge.amount = je.value("amount_eur_bn", 0.0f);
            edge.is_secured = je.value("is_secured", false);
            sim.edges.push_back(edge);
        }
    }

    // Apply pre-shock states (these have richer data than network nodes)
    if (data.contains("pre_shock") && data["pre_shock"].contains("bank_states")) {
        for (auto& [id, js] : data["pre_shock"]["bank_states"].items()) {
            for (auto& n : sim.nodes) {
                if (n.id == id) {
                    n.status = js.value("status", n.status);
                    n.total_assets = js.value("total_assets_eur_bn", n.total_assets);
                    n.cet1_ratio_pct = js.value("cet1_ratio_pct", n.cet1_ratio_pct);
                    n.lcr_pct = js.value("lcr_pct", n.lcr_pct);
                    break;
                }
            }
        }
    }

    // Parse rounds
    if (data.contains("rounds")) {
        for (auto& jr : data["rounds"]) {
            RoundState round;
            round.round_num = jr.value("round_num", 0);
            round.label = jr.value("label", "");
            round.round_loss = jr.value("round_loss_eur_bn", 0.0f);
            round.cumulative_loss = jr.value("cumulative_loss_eur_bn", 0.0f);

            // Bank states this round
            if (jr.contains("bank_states")) {
                for (auto& [id, js] : jr["bank_states"].items()) {
                    round.bank_states[id] = parse_bank_state(js);
                }
            }

            // Active contagion edges
            if (jr.contains("active_edges")) {
                for (auto& je : jr["active_edges"]) {
                    ContagionEdge ce;
                    ce.source = je.value("source", "");
                    ce.target = je.value("target", "");
                    round.active_edges.push_back(ce);
                }
            }

            // Affected banks
            if (jr.contains("affected_banks")) {
                for (auto& jb : jr["affected_banks"])
                    round.affected_banks.push_back(jb.get<std::string>());
            }

            // Metrics
            if (jr.contains("metrics")) {
                auto& jm = jr["metrics"];
                round.banks_stressed = jm.value("banks_stressed", 0);
                round.banks_failed = jm.value("banks_failed", 0);
                round.banks_normal = jm.value("banks_normal", 0);
            }

            sim.rounds.push_back(round);
        }
    }

    compute_layout(sim);
    sim.loaded = true;

    std::cout << "Loaded: " << sim.nodes.size() << " banks, "
              << sim.edges.size() << " edges, "
              << sim.rounds.size() << " rounds" << std::endl;
    return sim;
}

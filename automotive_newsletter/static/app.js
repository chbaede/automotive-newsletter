document.addEventListener("DOMContentLoaded", () => {
  if (window.lucide) {
    window.lucide.createIcons();
  }

  const status = document.querySelector("[data-status]");
  const collectForm = document.querySelector("[data-collect-form]");
  const sendForm = document.querySelector("[data-send-form]");
  const mailSettingsForm = document.querySelector("[data-mail-settings-form]");
  const passwordState = document.querySelector("[data-password-state]");
  const regionButtons = Array.from(document.querySelectorAll("[data-region-filter]"));
  const topicButtons = Array.from(document.querySelectorAll("[data-topic-filter]"));
  const sourceTypeButtons = Array.from(document.querySelectorAll("[data-source-type-filter]"));
  const issueSections = Array.from(document.querySelectorAll(".issue-section"));
  const filterEmpty = document.querySelector("[data-filter-empty]");
  const viewTabs = Array.from(document.querySelectorAll("[data-view-tab]"));
  const viewPanels = Array.from(document.querySelectorAll("[data-view-panel]"));
  const sourceHealthAction = document.querySelector("[data-source-health-action]");
  const sourceHealthSummary = document.querySelector("[data-source-health-summary]");
  const sourceHealthList = document.querySelector("[data-source-health-list]");

  const showStatus = (message, tone = "neutral") => {
    if (!status) return;
    status.textContent = message;
    status.dataset.tone = tone;
  };

  const getAdminKey = () => localStorage.getItem("admin_key") || "";

  const adminHeaders = () => {
    const key = getAdminKey();
    return key ? { "X-Admin-Key": key, "Authorization": `Bearer ${key}` } : {};
  };

  const checkAdminMode = () => {
    const key = getAdminKey();
    if (key) {
      document.body.classList.add("admin-mode");
    } else {
      document.body.classList.remove("admin-mode");
    }
  };

  checkAdminMode();

  // Secret trigger: clicking .brand-mark 5 times
  const brandMark = document.querySelector(".brand-mark");
  if (brandMark) {
    let clickCount = 0;
    let clickTimer = null;
    brandMark.addEventListener("click", () => {
      clickCount += 1;
      clearTimeout(clickTimer);
      clickTimer = setTimeout(() => {
        clickCount = 0;
      }, 2500);

      if (clickCount >= 5) {
        clickCount = 0;
        const currentKey = getAdminKey();
        if (currentKey) {
          if (confirm("관리자 모드를 종료(로그아웃)하시겠습니까?")) {
            localStorage.removeItem("admin_key");
            checkAdminMode();
            showStatus("관리자 모드가 해제되었습니다.");
          }
        } else {
          const input = prompt("관리자 키(비밀번호)를 입력하세요:");
          if (input !== null && input.trim()) {
            localStorage.setItem("admin_key", input.trim());
            checkAdminMode();
            showStatus("관리자 모드가 활성화되었습니다.");
          }
        }
      }
    });
  }

  if (collectForm) {
    collectForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      showStatus("뉴스를 수집하고 있습니다. 잠시만 기다려 주세요.");
      const button = collectForm.querySelector("button");
      button.disabled = true;
      try {
        const response = await fetch("/api/collect", {
          method: "POST",
          headers: adminHeaders(),
        });
        const payload = await response.json();
        if (!response.ok || !payload.ok) {
          if (response.status === 401) {
            localStorage.removeItem("admin_key");
            checkAdminMode();
          }
          throw new Error(payload.message || "수집에 실패했습니다.");
        }
        window.location.href = `/issues/${payload.issue_date}`;
      } catch (error) {
        showStatus(error.message, "error");
        button.disabled = false;
      }
    });
  }

  if (viewTabs.length > 0) {
    const showView = (target) => {
      viewTabs.forEach((button) => {
        const isActive = button.dataset.viewTab === target;
        button.classList.toggle("active", isActive);
        button.setAttribute("aria-pressed", isActive ? "true" : "false");
      });
      viewPanels.forEach((panel) => {
        panel.hidden = panel.dataset.viewPanel !== target;
      });
    };

    viewTabs.forEach((button) => {
      button.addEventListener("click", () => {
        showView(button.dataset.viewTab || "news");
      });
    });
  }

  if (regionButtons.length > 0 || topicButtons.length > 0 || sourceTypeButtons.length > 0) {
    const activeFilters = {
      region: "all",
      topic: "all",
      sourceType: "all",
    };

    const applyFilters = () => {
      let totalVisible = 0;

      regionButtons.forEach((button) => {
        const isActive = button.dataset.regionFilter === activeFilters.region;
        button.classList.toggle("active", isActive);
        button.setAttribute("aria-pressed", isActive ? "true" : "false");
      });

      topicButtons.forEach((button) => {
        const isActive = button.dataset.topicFilter === activeFilters.topic;
        button.classList.toggle("active", isActive);
        button.setAttribute("aria-pressed", isActive ? "true" : "false");
      });

      sourceTypeButtons.forEach((button) => {
        const isActive = button.dataset.sourceTypeFilter === activeFilters.sourceType;
        button.classList.toggle("active", isActive);
        button.setAttribute("aria-pressed", isActive ? "true" : "false");
      });

      issueSections.forEach((section) => {
        const cards = Array.from(section.querySelectorAll(".article-card"));
        let visibleCount = 0;

        cards.forEach((card) => {
          const regions = (card.dataset.filterRegions || card.dataset.regions || "").split(/\s+/).filter(Boolean);
          const topics = (card.dataset.topics || "").split(/\s+/).filter(Boolean);
          const sourceType = card.dataset.sourceType || "media";

          const matchRegion = activeFilters.region === "all" || regions.includes(activeFilters.region);
          const matchTopic = activeFilters.topic === "all" || topics.includes(activeFilters.topic);
          const matchSourceType = activeFilters.sourceType === "all" || sourceType === activeFilters.sourceType;

          const isVisible = matchRegion && matchTopic && matchSourceType;
          card.hidden = !isVisible;
          if (isVisible) {
            visibleCount += 1;
          }
        });

        const count = section.querySelector("[data-section-count]");
        if (count) {
          count.textContent = `${visibleCount}건`;
        }
        section.hidden = visibleCount === 0;
        totalVisible += visibleCount;
      });

      if (filterEmpty) {
        filterEmpty.hidden = totalVisible > 0;
      }
    };

    regionButtons.forEach((button) => {
      button.addEventListener("click", () => {
        activeFilters.region = button.dataset.regionFilter || "all";
        applyFilters();
      });
    });

    topicButtons.forEach((button) => {
      button.addEventListener("click", () => {
        activeFilters.topic = button.dataset.topicFilter || "all";
        applyFilters();
      });
    });

    sourceTypeButtons.forEach((button) => {
      button.addEventListener("click", () => {
        activeFilters.sourceType = button.dataset.sourceTypeFilter || "all";
        applyFilters();
      });
    });
  }

  if (mailSettingsForm) {
    mailSettingsForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      showStatus("메일 설정을 저장하고 있습니다.");
      const button = mailSettingsForm.querySelector("button");
      const formData = new FormData(mailSettingsForm);
      const passwordInput = mailSettingsForm.querySelector('input[name="smtp_password"]');
      button.disabled = true;
      try {
        const payload = {
          smtp_host: formData.get("smtp_host") || "",
          smtp_port: formData.get("smtp_port") || "587",
          smtp_user: formData.get("smtp_user") || "",
          smtp_password: formData.get("smtp_password") || "",
          smtp_from: formData.get("smtp_from") || "",
          newsletter_to: formData.get("newsletter_to") || "",
          smtp_tls: formData.has("smtp_tls"),
        };
        const response = await fetch("/api/settings/mail", {
          method: "POST",
          headers: { "Content-Type": "application/json", ...adminHeaders() },
          body: JSON.stringify(payload),
        });
        const result = await response.json();
        if (!response.ok || !result.ok) {
          if (response.status === 401) {
            localStorage.removeItem("admin_key");
            checkAdminMode();
          }
          throw new Error(result.message || "메일 설정 저장에 실패했습니다.");
        }
        if (passwordInput) {
          passwordInput.value = "";
          passwordInput.placeholder = result.settings.smtp_password_saved
            ? "비워두면 기존 값 유지"
            : "비밀번호 또는 앱 비밀번호";
        }
        if (passwordState) {
          passwordState.textContent = result.settings.smtp_password_saved
            ? "비밀번호 저장됨"
            : "비밀번호 미저장";
        }
        showStatus("메일 설정을 저장했습니다.", "success");
      } catch (error) {
        showStatus(error.message, "error");
      } finally {
        button.disabled = false;
      }
    });
  }

  if (sourceHealthAction && sourceHealthList && sourceHealthSummary) {
    const renderSourceHealth = (sources) => {
      const okCount = sources.filter((source) => source.ok).length;
      const fallbackCount = sources.filter((source) => source.tls_fallback).length;
      
      const summaryKo = `${okCount}/${sources.length}개 소스 연결됨${fallbackCount ? ` · TLS 우회 ${fallbackCount}개` : ""}`;
      const summaryEn = `${okCount}/${sources.length} sources connected${fallbackCount ? ` · TLS bypass ${fallbackCount}` : ""}`;
      
      sourceHealthSummary.innerHTML = `
        <span class="lang-ko">${summaryKo}</span>
        <span class="lang-en" style="display:none;">${summaryEn}</span>
      `;
      
      sourceHealthList.innerHTML = "";
      sources.forEach((source) => {
        const item = document.createElement("article");
        item.className = `source-health-item ${source.ok ? "is-ok" : "is-fail"}`;
        
        const statusKo = source.ok ? "정상" : "실패";
        const statusEn = source.ok ? "OK" : "Failed";
        const entries = Number(source.entries || 0);
        
        const tlsKo = source.tls_fallback ? "TLS 우회" : `HTTP ${source.status_code || "-"}`;
        const tlsEn = source.tls_fallback ? "TLS Bypass" : `HTTP ${source.status_code || "-"}`;
        
        item.innerHTML = `
          <div>
            <strong>${source.name}</strong>
            <span class="lang-ko">${source.bucket} · ${entries}건 · ${statusKo}</span>
            <span class="lang-en" style="display:none;">${source.bucket} · ${entries} items · ${statusEn}</span>
          </div>
          <small>
            <span class="lang-ko">${tlsKo}</span>
            <span class="lang-en" style="display:none;">${tlsEn}</span>
          </small>
        `;
        if (source.error) {
          const error = document.createElement("code");
          error.textContent = source.error;
          item.appendChild(error);
        }
        sourceHealthList.appendChild(item);
      });
    };

    sourceHealthAction.addEventListener("click", async () => {
      sourceHealthAction.disabled = true;
      sourceHealthSummary.innerHTML = `
        <span class="lang-ko">외부 소스를 확인하고 있습니다.</span>
        <span class="lang-en" style="display:none;">Checking external sources.</span>
      `;
      try {
        const response = await fetch("/api/sources/health");
        const payload = await response.json();
        if (!response.ok || !payload.ok) {
          throw new Error(payload.message || "소스 상태 확인에 실패했습니다.");
        }
        renderSourceHealth(payload.sources || []);
      } catch (error) {
        sourceHealthSummary.textContent = error.message;
      } finally {
        sourceHealthAction.disabled = false;
      }
    });
  }

  if (sendForm) {
    sendForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const issueDate = sendForm.dataset.issueDate;
      showStatus("메일 발송을 시도하고 있습니다.");
      const button = sendForm.querySelector("button");
      button.disabled = true;
      try {
        const lang = document.documentElement.classList.contains("lang-en-active") ? "en" : "ko";
        const response = await fetch(`/api/issues/${issueDate}/send?lang=${lang}`, {
          method: "POST",
          headers: adminHeaders(),
        });
        const payload = await response.json();
        if (!response.ok || !payload.ok) {
          if (response.status === 401) {
            localStorage.removeItem("admin_key");
            checkAdminMode();
          }
          throw new Error(payload.message || "메일 발송에 실패했습니다.");
        }
        showStatus(payload.message, "success");
      } catch (error) {
        showStatus(error.message, "error");
      } finally {
        button.disabled = false;
      }
    });
  }

  const langToggle = document.querySelector("[data-lang-toggle]");
  if (langToggle) {
    const textSpan = langToggle.querySelector(".lang-text");
    
    // Initialize language from localStorage
    const savedLang = localStorage.getItem("preferred_lang");
    if (savedLang === "en") {
      document.documentElement.classList.add("lang-en-active");
      if (textSpan) textSpan.textContent = "KO";
    }

    langToggle.addEventListener("click", () => {
      document.documentElement.classList.toggle("lang-en-active");
      const isEn = document.documentElement.classList.contains("lang-en-active");
      if (textSpan) {
        textSpan.textContent = isEn ? "KO" : "EN";
      }
      localStorage.setItem("preferred_lang", isEn ? "en" : "ko");
    });
  }
});

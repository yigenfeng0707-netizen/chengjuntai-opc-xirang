# -*- coding: utf-8 -*-
"""
LLM 统一客户端 —— OpenAI 兼容多 provider 级联 fallback
按 config.yaml 中 llm.providers 顺序逐个尝试，任一成功即返回其 content；
全部失败才返回调用方传入的 fallback（保证流水线可跑通）。

兼容两种配置形态：
  · 新格式：llm.providers 列表（推荐，支持多级降级）
  · 旧格式：llm.api_base / api_key / model 扁平字段（向后兼容）
"""
import requests
import op_logger
from config_loader import load_config


def _get_providers() -> list:
    """读取当前生效的 provider 列表；Llm 未启用或未配置时返回 []"""
    cfg = load_config().get("llm", {})
    if not cfg.get("enabled", False):
        return []

    # 新格式：显式 providers 列表
    providers_cfg = cfg.get("providers")
    if isinstance(providers_cfg, list) and providers_cfg:
        out = []
        for p in providers_cfg:
            if not p.get("enabled", True):
                continue
            if p.get("api_base") and p.get("api_key") and p.get("model"):
                p.setdefault("name", p.get("api_base", "?"))
                out.append(p)
        return out

    # 旧格式：扁平单 provider
    if cfg.get("api_base") and cfg.get("api_key"):
        return [{
            "name": "default",
            "api_base": cfg["api_base"],
            "api_key": cfg["api_key"],
            "model": cfg.get("model", "gpt-4o-mini"),
            "timeout": cfg.get("timeout", 60),
        }]
    return []


def is_llm_enabled() -> bool:
    """是否有任意一个可用 provider"""
    return len(_get_providers()) > 0


def call_llm(prompt: str, fallback: str = "", max_tokens: int = None,
             temperature: float = None, timeout: int = None,
             reverse_order: bool = False, thinking: object = None,
             system_prompt: str = None) -> str:
    """
    级联调用 LLM。
    - 逐个尝试 provider，HTTP 200 且 content 非空即返回（content 已 strip）。
    - 全部失败返回 fallback。
    - reverse_order=True 时反转 provider 顺序（最强模型优先），适用于 NL2SQL 等
      对推理质量要求高、可容忍较长延迟的场景。
    - thinking: None=使用 config 配置；True=强制开启推理模型思考（适用于 NL2SQL 等
      复杂推理任务）；False=强制关闭。开启思考可显著提升推理质量但增加延迟。
    - system_prompt: 若提供，则发送 system+user 双消息（NL2SQL 等场景用 system 消息
      传递 schema 和规则，用 user 消息传递具体问题，比全塞 user 消息效果好得多）。
    - 推理模型（qwen3.7-max / sensenova-flash / step-flash）的最终答案
      都在标准 message.content 字段，推理过程在 reasoning / reasoning_content
      字段（无需清理，直接舍去）。
    """
    cfg = load_config().get("llm", {})
    providers = _get_providers()
    if not providers:
        return fallback

    if reverse_order:
        providers = list(reversed(providers))

    temp = temperature if temperature is not None else cfg.get("temperature", 0.7)
    mt = max_tokens if max_tokens is not None else cfg.get("max_tokens", 4096)
    think = cfg.get("enable_thinking", None)  # None=不传；False=关闭思考(推理模型提速)
    if thinking is not None:
        think = thinking  # 调用方显式覆盖

    # 构建消息列表：system_prompt 存在时用双消息，否则单 user 消息
    if system_prompt:
        messages = [{"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}]
    else:
        messages = [{"role": "user", "content": prompt}]

    for p in providers:
        name = p.get("name", "?")
        model = p["model"]
        tmo = timeout if timeout is not None else p.get("timeout", 60)
        try:
            req_body = {"model": model,
                        "messages": messages,
                        "temperature": temp,
                        "max_tokens": mt}
            # 关闭推理模型思考过程（阿里云qwen3.7-max生效且提速近1倍；其它provider安全忽略）
            if think is not None:
                req_body["enable_thinking"] = think
            r = requests.post(
                f"{p['api_base']}/chat/completions",
                headers={"Authorization": f"Bearer {p['api_key']}",
                         "Content-Type": "application/json"},
                json=req_body,
                timeout=tmo,
            )
            if r.status_code == 200:
                content = (r.json()
                           .get("choices", [{}])[0]
                           .get("message", {})
                           .get("content", ""))
                if content and content.strip():
                    op_logger.log("llm_client",
                                  f"LLM调用成功[{name}/{model}]",
                                  level="INFO")
                    return content.strip()
                op_logger.log("llm_client",
                              f"LLM返回空content[{name}/{model}] http={r.status_code}",
                              level="WARN")
            else:
                op_logger.log("llm_client",
                              f"LLM HTTP{r.status_code}[{name}/{model}]: {r.text[:200]}",
                              level="WARN")
        except Exception as ex:
            op_logger.log("llm_client",
                          f"LLM调用异常[{name}/{model}]: {ex}",
                          level="WARN")

    op_logger.log("llm_client", "所有 provider 均失败，降级 fallback", level="WARN")
    return fallback


if __name__ == "__main__":
    # 自检：打印生效的 provider 列表并做一次最小调用
    ps = _get_providers()
    print(f"生效 provider 数: {len(ps)}")
    for p in ps:
        print(f"  - {p.get('name')}: {p['model']} @ {p['api_base']}")
    if ps:
        ans = call_llm("用一句话说明什么是MCP协议。", max_tokens=2000)
        print("\nLLM 回复:", ans[:200])

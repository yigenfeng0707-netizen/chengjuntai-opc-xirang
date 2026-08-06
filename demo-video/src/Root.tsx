import { AbsoluteFill, Audio, Sequence, Composition, useVideoConfig, Img, staticFile, interpolate, spring, useCurrentFrame, Easing } from "remotion";
import shotsData from "../public/shots.json";

// ==================== Types ====================
interface Shot {
  id: string;
  startFrame: number;
  durationInFrames: number;
  audio: string;
  audioDurationSec: number;
  narration: string;
  visual: string;
  action: string;
  visualType: string;
  bg: string;
  transition: string;
}

interface ShotsData {
  fps: number;
  width: number;
  height: number;
  title: string;
  totalFrames: number;
  shots: Shot[];
}

const data = shotsData as ShotsData;

// ==================== Color Palette ====================
const COLORS = {
  bg: "#0F172A",
  bgGradient: "#1E3A5F",
  primary: "#3B82F6",
  accent: "#06B6D4",
  accent2: "#8B5CF6",
  success: "#10B981",
  warning: "#F59E0B",
  danger: "#EF4444",
  text: "#F8FAFC",
  textDim: "#94A3B8",
  cardBg: "rgba(30, 41, 59, 0.8)",
  cardBorder: "rgba(59, 130, 246, 0.3)",
};

// ==================== Helper: fade transition ====================
const useFadeTransition = (frame: number, durationInFrames: number, transition: string) => {
  const fadeFrames = 10;
  let opacity = 1;
  let transform = "";

  // Fade in
  if (frame < fadeFrames) {
    opacity = interpolate(frame, [0, fadeFrames], [0, 1], { extrapolateRight: "clamp" });
  }
  // Fade out
  if (frame > durationInFrames - fadeFrames) {
    opacity = interpolate(frame, [durationInFrames - fadeFrames, durationInFrames], [1, 0], { extrapolateLeft: "clamp" });
  }

  // Transition-specific transform
  const progress = spring({
    frame,
    fps: 30,
    config: { damping: 200 },
    durationInFrames: 20,
  });

  switch (transition) {
    case "slide-left":
      transform = `translateX(${interpolate(progress, [0, 1], [100, 0])}px)`;
      break;
    case "slide-right":
      transform = `translateX(${interpolate(progress, [0, 1], [-100, 0])}px)`;
      break;
    case "slide-up":
      transform = `translateY(${interpolate(progress, [0, 1], [100, 0])}px)`;
      break;
    case "zoom-in":
      const scaleIn = interpolate(progress, [0, 1], [0.8, 1]);
      transform = `scale(${scaleIn})`;
      break;
    case "zoom-out":
      const scaleOut = interpolate(progress, [0, 1], [1.2, 1]);
      transform = `scale(${scaleOut})`;
      break;
    default:
      break;
  }

  return { opacity, transform };
};

// ==================== Subtitle Bar ====================
const SubtitleBar: React.FC<{ narration: string; durationInFrames: number }> = ({ narration, durationInFrames }) => {
  const frame = useCurrentFrame();
  const fadeFrames = 8;

  let opacity = 1;
  if (frame < fadeFrames) {
    opacity = interpolate(frame, [0, fadeFrames], [0, 1], { extrapolateRight: "clamp" });
  }
  if (frame > durationInFrames - fadeFrames) {
    opacity = interpolate(frame, [durationInFrames - fadeFrames, durationInFrames], [1, 0], { extrapolateLeft: "clamp" });
  }

  return (
    <div style={{
      position: "absolute",
      bottom: 60,
      left: "50%",
      transform: "translateX(-50%)",
      opacity,
      maxWidth: "80%",
      padding: "12px 32px",
      background: "rgba(0, 0, 0, 0.75)",
      borderRadius: 8,
      backdropFilter: "blur(8px)",
      border: `1px solid ${COLORS.cardBorder}`,
    }}>
      <span style={{
        color: COLORS.text,
        fontSize: 28,
        fontFamily: "'Microsoft YaHei', 'PingFang SC', sans-serif",
        fontWeight: 500,
        textShadow: "0 2px 8px rgba(0,0,0,0.8)",
      }}>
        {narration}
      </span>
    </div>
  );
};

// ==================== Background ====================
const GradientBg: React.FC<{ bg: string }> = ({ bg }) => {
  return (
    <AbsoluteFill>
      <div style={{
        width: "100%",
        height: "100%",
        background: `linear-gradient(135deg, ${bg} 0%, ${COLORS.bgGradient} 50%, ${bg} 100%)`,
      }} />
      {/* Particle dots */}
      <div style={{
        position: "absolute",
        inset: 0,
        backgroundImage: `radial-gradient(circle at 20% 30%, rgba(59,130,246,0.15) 0%, transparent 40%),
                          radial-gradient(circle at 80% 70%, rgba(139,92,246,0.1) 0%, transparent 40%),
                          radial-gradient(circle at 50% 50%, rgba(6,182,212,0.08) 0%, transparent 50%)`,
      }} />
    </AbsoluteFill>
  );
};

// ==================== Shot Components ====================

// Shot 01: Cover - title spring in
const ShotCover: React.FC<{ shot: Shot }> = ({ shot }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { opacity, transform } = useFadeTransition(frame, shot.durationInFrames, shot.transition);

  const titleScale = spring({
    frame,
    fps,
    config: { damping: 12, mass: 1, stiffness: 100 },
    durationInFrames: 30,
  });

  const subtitleOpacity = interpolate(frame, [20, 50], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const footerOpacity = interpolate(frame, [40, 70], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  return (
    <AbsoluteFill style={{ opacity, transform, justifyContent: "center", alignItems: "center" }}>
      <GradientBg bg={shot.bg} />
      <div style={{
        transform: `scale(${titleScale})`,
        textAlign: "center",
        zIndex: 10,
      }}>
        <h1 style={{
          color: COLORS.text,
          fontSize: 120,
          fontWeight: 800,
          fontFamily: "'Microsoft YaHei', sans-serif",
          margin: 0,
          textShadow: `0 0 60px ${COLORS.primary}88, 0 4px 20px rgba(0,0,0,0.5)`,
          letterSpacing: "0.1em",
        }}>
          成军台
        </h1>
      </div>
      <div style={{
        position: "absolute",
        top: "58%",
        opacity: subtitleOpacity,
        textAlign: "center",
      }}>
        <span style={{
          color: COLORS.accent,
          fontSize: 44,
          fontFamily: "'Microsoft YaHei', sans-serif",
          fontWeight: 400,
          letterSpacing: "0.3em",
        }}>
          息壤育智 · 一人成军
        </span>
      </div>
      <div style={{
        position: "absolute",
        bottom: 120,
        opacity: footerOpacity,
      }}>
        <span style={{
          color: COLORS.textDim,
          fontSize: 24,
          fontFamily: "'Microsoft YaHei', sans-serif",
        }}>
          2026 息壤杯 · 惠民 · AI+自选开放场景
        </span>
      </div>
    </AbsoluteFill>
  );
};

// Shot 02: Bullets - pain points
const ShotBullets: React.FC<{ shot: Shot }> = ({ shot }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { opacity, transform } = useFadeTransition(frame, shot.durationInFrames, shot.transition);

  const items = [
    { title: "Chat套壳不可验收", icon: "M9 12l2 2 4-4", color: COLORS.danger },
    { title: "无协作机制", icon: "M17 20h5v-2a4 4 0 00-3-3.87M9 20H4v-2a4 4 0 013-3.87m6-5.13a4 4 0 11-8 0 4 4 0 018 0zm6 0a4 4 0 11-8 0 4 4 0 018 0z", color: COLORS.warning },
    { title: "无周报导出", icon: "M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z", color: COLORS.accent2 },
  ];

  return (
    <AbsoluteFill style={{ opacity, transform }}>
      <GradientBg bg={shot.bg} />
      <div style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        width: "100%",
        height: "100%",
        gap: 60,
      }}>
        {/* Left: big text */}
        <div style={{ flex: "0 0 40%", textAlign: "center" }}>
          <span style={{
            color: COLORS.text,
            fontSize: 56,
            fontWeight: 700,
            fontFamily: "'Microsoft YaHei', sans-serif",
            lineHeight: 1.5,
            display: "block",
          }}>
            一个人创业
          </span>
          <span style={{
            color: COLORS.warning,
            fontSize: 56,
            fontWeight: 700,
            fontFamily: "'Microsoft YaHei', sans-serif",
            lineHeight: 1.5,
          }}>
            活是一支团队的量
          </span>
        </div>
        {/* Right: pain point cards */}
        <div style={{ flex: "0 0 35%", display: "flex", flexDirection: "column", gap: 24 }}>
          {items.map((item, i) => {
            const slideIn = spring({
              frame: frame - 15 - i * 6,
              fps,
              config: { damping: 15 },
              durationInFrames: 20,
            });
            const x = interpolate(slideIn, [0, 1], [200, 0]);
            const cardOpacity = interpolate(slideIn, [0, 1], [0, 1]);
            return (
              <div key={i} style={{
                opacity: cardOpacity,
                transform: `translateX(${x}px)`,
                background: COLORS.cardBg,
                border: `1px solid ${item.color}44`,
                borderRadius: 16,
                padding: "24px 32px",
                boxShadow: `0 4px 24px ${item.color}22`,
                display: "flex",
                alignItems: "center",
                gap: 16,
              }}>
                <div style={{
                  width: 48,
                  height: 48,
                  borderRadius: 12,
                  background: `${item.color}22`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                }}>
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke={item.color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d={item.icon} />
                  </svg>
                </div>
                <span style={{
                  color: COLORS.text,
                  fontSize: 28,
                  fontFamily: "'Microsoft YaHei', sans-serif",
                  fontWeight: 500,
                }}>
                  {item.title}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};

// Shot 03: Section - solution overview
const ShotSection: React.FC<{ shot: Shot }> = ({ shot }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { opacity, transform } = useFadeTransition(frame, shot.durationInFrames, shot.transition);

  const roles = [
    { name: "调研", color: COLORS.accent, angle: 0 },
    { name: "内容", color: COLORS.accent2, angle: 72 },
    { name: "数据", color: COLORS.success, angle: 144 },
    { name: "运营", color: COLORS.warning, angle: 216 },
    { name: "复盘", color: COLORS.primary, angle: 288 },
  ];

  const centerX = 960;
  const centerY = 540;
  const radius = 280;

  return (
    <AbsoluteFill style={{ opacity, transform }}>
      <GradientBg bg={shot.bg} />
      <div style={{
        position: "absolute",
        top: "15%",
        width: "100%",
        textAlign: "center",
      }}>
        <span style={{
          color: COLORS.text,
          fontSize: 56,
          fontWeight: 700,
          fontFamily: "'Microsoft YaHei', sans-serif",
        }}>
          目标驱动 · AI员工矩阵 · 可验收
        </span>
      </div>
      {/* Center hub */}
      <div style={{
        position: "absolute",
        left: centerX - 110,
        top: centerY - 110,
        width: 220,
        height: 220,
        borderRadius: "50%",
        background: `linear-gradient(135deg, ${COLORS.primary}, ${COLORS.accent})`,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        boxShadow: `0 0 60px ${COLORS.primary}66`,
        zIndex: 5,
      }}>
        <span style={{ color: "white", fontSize: 28, fontWeight: 700, fontFamily: "'Microsoft YaHei', sans-serif", whiteSpace: "nowrap" }}>
          司令Agent
        </span>
      </div>
      {/* Role nodes */}
      {roles.map((role, i) => {
        const rad = (role.angle * Math.PI) / 180;
        const x = centerX + radius * Math.cos(rad) - 60;
        const y = centerY + radius * Math.sin(rad) - 60;
        const expand = spring({
          frame: frame - 15 - i * 5,
          fps,
          config: { damping: 12 },
          durationInFrames: 25,
        });
        const scale = interpolate(expand, [0, 1], [0, 1]);
        const nodeOpacity = interpolate(expand, [0, 1], [0, 1]);

        return (
          <div key={i} style={{
            position: "absolute",
            left: x,
            top: y,
            width: 120,
            height: 120,
            borderRadius: "50%",
            background: `${role.color}22`,
            border: `2px solid ${role.color}`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            opacity: nodeOpacity,
            transform: `scale(${scale})`,
            boxShadow: `0 0 30px ${role.color}44`,
          }}>
            <span style={{ color: role.color, fontSize: 24, fontWeight: 600, fontFamily: "'Microsoft YaHei', sans-serif" }}>
              {role.name}
            </span>
          </div>
        );
      })}
    </AbsoluteFill>
  );
};

// Shot 04: Login page mockup (standalone component for reliability)
const ShotLogin: React.FC<{ shot: Shot }> = ({ shot }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { opacity, transform } = useFadeTransition(frame, shot.durationInFrames, shot.transition);

  const cardScale = spring({
    frame,
    fps,
    config: { damping: 12 },
    durationInFrames: 25,
  });

  // Replace CSS pulse with Remotion interpolate
  const pulseScale = 1 + Math.sin(frame * 0.15) * 0.04;
  const ctaOpacity = interpolate(frame, [15, 30], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  return (
    <AbsoluteFill style={{ opacity, transform }}>
      <GradientBg bg={shot.bg} />
      <div style={{
        position: "relative",
        zIndex: 10,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        width: "100%",
        height: "100%",
      }}>
        <div style={{
          transform: `scale(${cardScale})`,
          background: COLORS.cardBg,
          border: `1px solid ${COLORS.cardBorder}`,
          borderRadius: 24,
          padding: "48px 64px",
          boxShadow: "0 8px 48px rgba(0,0,0,0.4)",
          textAlign: "center",
        }}>
          <div style={{ color: COLORS.text, fontSize: 36, marginBottom: 24, fontFamily: "'Microsoft YaHei', sans-serif", fontWeight: 700 }}>
            评委60秒体验
          </div>
          <div style={{
            background: `linear-gradient(135deg, ${COLORS.success}, ${COLORS.accent})`,
            color: "white",
            fontSize: 28,
            fontWeight: 700,
            padding: "16px 48px",
            borderRadius: 12,
            fontFamily: "'Microsoft YaHei', sans-serif",
            transform: `scale(${pulseScale})`,
            opacity: ctaOpacity,
            boxShadow: `0 0 30px ${COLORS.success}66`,
            display: "inline-block",
          }}>
            点击进入 →
          </div>
          <div style={{ color: COLORS.textDim, fontSize: 20, marginTop: 20, fontFamily: "'Microsoft YaHei', sans-serif" }}>
            零讲解 · 评委自己点
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

// Shot 05: Dashboard mockup (standalone component for reliability)
const ShotDashboard: React.FC<{ shot: Shot }> = ({ shot }) => {
  const frame = useCurrentFrame();
  const { opacity, transform } = useFadeTransition(frame, shot.durationInFrames, shot.transition);

  const headerOpacity = interpolate(frame, [5, 20], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const cardOpacity = interpolate(frame, [15, 30], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const taskOpacity = interpolate(frame, [30, 45], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  return (
    <AbsoluteFill style={{ opacity, transform }}>
      <GradientBg bg={shot.bg} />
      <div style={{
        position: "relative",
        zIndex: 10,
        display: "flex",
        flexDirection: "column",
        padding: "40px 60px",
        width: "100%",
        height: "100%",
      }}>
        <div style={{
          background: `linear-gradient(90deg, ${COLORS.primary}, ${COLORS.accent})`,
          color: "white",
          fontSize: 28,
          fontWeight: 700,
          padding: "12px 24px",
          borderRadius: 8,
          marginBottom: 24,
          fontFamily: "'Microsoft YaHei', sans-serif",
          opacity: headerOpacity,
        }}>
          本周故事
        </div>
        <div style={{
          background: COLORS.cardBg,
          border: `2px solid ${COLORS.primary}`,
          borderRadius: 16,
          padding: 24,
          marginBottom: 20,
          opacity: cardOpacity,
        }}>
          <span style={{ color: COLORS.text, fontSize: 32, fontWeight: 600, fontFamily: "'Microsoft YaHei', sans-serif" }}>
            AI获客跟进
          </span>
          <div style={{ marginTop: 12, height: 8, background: "rgba(255,255,255,0.1)", borderRadius: 4, overflow: "hidden" }}>
            <div style={{
              width: `${interpolate(frame, [20, shot.durationInFrames - 20], [0, 100], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })}%`,
              height: "100%",
              background: `linear-gradient(90deg, ${COLORS.success}, ${COLORS.accent})`,
              borderRadius: 4,
            }} />
          </div>
        </div>
        {/* Task tree */}
        <div style={{ display: "flex", gap: 16, alignItems: "center", opacity: taskOpacity }}>
          {["计划", "执行", "人审", "完成"].map((step, i) => {
            const highlight = frame > 30 + i * 15;
            return (
              <div key={i} style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
              }}>
                <div style={{
                  padding: "8px 20px",
                  borderRadius: 8,
                  background: highlight ? `${COLORS.success}33` : "rgba(255,255,255,0.05)",
                  border: `1px solid ${highlight ? COLORS.success : "rgba(255,255,255,0.1)"}`,
                }}>
                  <span style={{
                    color: highlight ? COLORS.success : COLORS.textDim,
                    fontSize: 22,
                    fontFamily: "'Microsoft YaHei', sans-serif",
                  }}>
                    {step}
                  </span>
                </div>
                {i < 3 && <span style={{ color: COLORS.textDim, fontSize: 20 }}>→</span>}
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};

// Shot 06-08: Captions - UI mockups (drawer, export, query)
const ShotCaptions: React.FC<{ shot: Shot }> = ({ shot }) => {
  const frame = useCurrentFrame();
  const { opacity, transform } = useFadeTransition(frame, shot.durationInFrames, shot.transition);

  const isDrawer = shot.id === "shot-06";
  const isExport = shot.id === "shot-07";
  const isQuery = shot.id === "shot-08";

  return (
    <AbsoluteFill style={{ opacity, transform }}>
      <GradientBg bg={shot.bg} />

      {isDrawer && (
        <div style={{
          position: "relative",
          zIndex: 10,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          height: "100%",
          gap: 20,
        }}>
          <div style={{ display: "flex", gap: 16 }}>
            {["调研", "内容", "数据", "运营", "复盘"].map((tab, i) => {
              const isActive = i === 1;
              const slideIn = spring({
                frame: frame - 10 - i * 4,
                fps: 30,
                config: { damping: 15 },
                durationInFrames: 15,
              });
              return (
                <div key={i} style={{
                  opacity: slideIn,
                  transform: `translateY(${interpolate(slideIn, [0, 1], [50, 0])}px)`,
                  padding: "12px 32px",
                  borderRadius: 8,
                  background: isActive ? `${COLORS.accent2}33` : "rgba(255,255,255,0.05)",
                  border: `1px solid ${isActive ? COLORS.accent2 : "rgba(255,255,255,0.1)"}`,
                }}>
                  <span style={{
                    color: isActive ? COLORS.accent2 : COLORS.textDim,
                    fontSize: 26,
                    fontWeight: isActive ? 700 : 400,
                    fontFamily: "'Microsoft YaHei', sans-serif",
                  }}>
                    {tab}
                  </span>
                </div>
              );
            })}
          </div>
          <div style={{
            background: COLORS.cardBg,
            border: `1px solid ${COLORS.accent2}44`,
            borderRadius: 12,
            padding: 24,
            width: "60%",
            opacity: interpolate(frame, [40, 60], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
          }}>
            <span style={{ color: COLORS.text, fontSize: 22, fontFamily: "'Microsoft YaHei', sans-serif" }}>
              内容官产物：种草文案草稿、配图建议、发布标签...
            </span>
            <div style={{
              marginTop: 16,
              display: "inline-block",
              padding: "6px 16px",
              background: `${COLORS.success}22`,
              border: `1px solid ${COLORS.success}`,
              borderRadius: 6,
            }}>
              <span style={{ color: COLORS.success, fontSize: 18, fontFamily: "'Microsoft YaHei', sans-serif" }}>
                可预览 · 可验收
              </span>
            </div>
          </div>
        </div>
      )}

      {isExport && (
        <div style={{
          position: "relative",
          zIndex: 10,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          height: "100%",
          gap: 30,
        }}>
          <div style={{
            padding: "16px 40px",
            background: `${COLORS.warning}22`,
            border: `2px solid ${COLORS.warning}`,
            borderRadius: 12,
            opacity: interpolate(frame, [0, 15], [0, 1], { extrapolateLeft: "clamp" }),
          }}>
            <span style={{ color: COLORS.warning, fontSize: 32, fontWeight: 700, fontFamily: "'Microsoft YaHei', sans-serif" }}>
              ① 导出Word
            </span>
          </div>
          <div style={{
            opacity: interpolate(frame, [20, 40], [0, 1], { extrapolateLeft: "clamp" }),
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 16,
          }}>
            <svg width="80" height="80" viewBox="0 0 24 24" fill={COLORS.success} style={{ filter: `drop-shadow(0 0 20px ${COLORS.success}66)` }}>
              <path d="M5 3l14 9-14 9V3z" />
            </svg>
            <span style={{ color: COLORS.text, fontSize: 28, fontWeight: 600, fontFamily: "'Microsoft YaHei', sans-serif" }}>
              成军周报.docx
            </span>
            <div style={{
              width: 200,
              height: 6,
              background: "rgba(255,255,255,0.1)",
              borderRadius: 3,
              overflow: "hidden",
            }}>
              <div style={{
                width: `${interpolate(frame, [30, 55], [0, 100], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })}%`,
                height: "100%",
                background: COLORS.success,
                borderRadius: 3,
              }} />
            </div>
          </div>
        </div>
      )}

      {isQuery && (
        <div style={{
          position: "relative",
          zIndex: 10,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          height: "100%",
          gap: 20,
        }}>
          <div style={{
            display: "flex",
            gap: 12,
            opacity: interpolate(frame, [0, 15], [0, 1], { extrapolateLeft: "clamp" }),
          }}>
            <div style={{
              background: COLORS.cardBg,
              border: `1px solid ${COLORS.cardBorder}`,
              borderRadius: 8,
              padding: "12px 24px",
              width: 400,
            }}>
              <span style={{ color: COLORS.text, fontSize: 24, fontFamily: "'Microsoft YaHei', sans-serif" }}>
                浙江政采标讯Top10
              </span>
            </div>
            <div style={{
              background: COLORS.primary,
              color: "white",
              borderRadius: 8,
              padding: "12px 24px",
              display: "flex",
              alignItems: "center",
            }}>
              <span style={{ fontSize: 22, fontFamily: "'Microsoft YaHei', sans-serif" }}>查询</span>
            </div>
          </div>
          {/* Data table */}
          <div style={{
            opacity: interpolate(frame, [20, 35], [0, 1], { extrapolateLeft: "clamp" }),
            width: "80%",
          }}>
            {["标题", "采购人", "预算", "地区", "日期", "类型", "状态", "链接"].map((col, ci) => (
              <div key={ci} style={{
                display: "inline-block",
                width: "12.5%",
                padding: "8px 4px",
                textAlign: "center",
                background: COLORS.cardBg,
                borderBottom: `1px solid ${COLORS.cardBorder}`,
              }}>
                <span style={{ color: COLORS.accent, fontSize: 18, fontFamily: "'Microsoft YaHei', sans-serif", fontWeight: 600 }}>
                  {col}
                </span>
              </div>
            ))}
            {Array.from({ length: 5 }).map((_, ri) => (
              <div key={ri} style={{ width: "100%" }}>
                {Array.from({ length: 8 }).map((_, ci) => (
                  <div key={ci} style={{
                    display: "inline-block",
                    width: "12.5%",
                    padding: "6px 4px",
                    textAlign: "center",
                    background: ri % 2 === 0 ? "rgba(15,23,42,0.6)" : "rgba(30,41,59,0.6)",
                  }}>
                    <span style={{ color: COLORS.textDim, fontSize: 16, fontFamily: "'Microsoft YaHei', sans-serif" }}>
                      {ri === 0 ? `数据${ri + 1}-${ci + 1}` : "—"}
                    </span>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>
      )}
    </AbsoluteFill>
  );
};

// Shot 09: Data metrics with counter animation
const ShotMetrics: React.FC<{ shot: Shot }> = ({ shot }) => {
  const frame = useCurrentFrame();
  const { opacity, transform } = useFadeTransition(frame, shot.durationInFrames, shot.transition);

  const metrics = [
    { label: "真实标讯", target: 312, color: COLORS.accent, unit: "条" },
    { label: "MCP工具", target: 15, color: COLORS.success, unit: "个" },
    { label: "LLM级联", target: 4, color: COLORS.warning, unit: "级" },
    { label: "AI角色", target: 5, color: COLORS.accent2, unit: "个" },
  ];

  return (
    <AbsoluteFill style={{ opacity, transform }}>
      <GradientBg bg={shot.bg} />
      <div style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        height: "100%",
        gap: 40,
      }}>
        {metrics.map((m, i) => {
          const cardScale = spring({
            frame: frame - 10 - i * 6,
            fps: 30,
            config: { damping: 12 },
            durationInFrames: 25,
          });
          const countProgress = interpolate(frame, [20 + i * 6, 60 + i * 6], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.out(Easing.cubic),
          });
          const currentVal = Math.round(m.target * countProgress);

          return (
            <div key={i} style={{
              opacity: cardScale,
              transform: `scale(${cardScale})`,
              background: COLORS.cardBg,
              border: `1px solid ${m.color}44`,
              borderRadius: 20,
              padding: "40px 48px",
              textAlign: "center",
              boxShadow: `0 4px 32px ${m.color}22`,
              minWidth: 240,
            }}>
              <div style={{
                color: m.color,
                fontSize: 80,
                fontWeight: 800,
                fontFamily: "'Microsoft YaHei', sans-serif",
                lineHeight: 1,
              }}>
                {currentVal}
              </div>
              <div style={{
                color: m.color,
                fontSize: 24,
                marginTop: 8,
                fontFamily: "'Microsoft YaHei', sans-serif",
              }}>
                {m.unit}
              </div>
              <div style={{
                color: COLORS.textDim,
                fontSize: 22,
                marginTop: 16,
                fontFamily: "'Microsoft YaHei', sans-serif",
              }}>
                {m.label}
              </div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

// Shot 10: LLM cascade diagram
const ShotLLMCascade: React.FC<{ shot: Shot }> = ({ shot }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { opacity, transform } = useFadeTransition(frame, shot.durationInFrames, shot.transition);

  const nodes = [
    { name: "息壤", role: "primary", color: COLORS.primary },
    { name: "TokenPlan", role: "1st fallback", color: COLORS.accent },
    { name: "壁韧", role: "2nd fallback", color: COLORS.warning },
    { name: "SenseNova", role: "3rd fallback", color: COLORS.accent2 },
  ];

  const nodeWidth = 200;
  const gap = 80;
  const startX = (1920 - (nodes.length * nodeWidth + (nodes.length - 1) * gap)) / 2;

  return (
    <AbsoluteFill style={{ opacity, transform }}>
      <GradientBg bg={shot.bg} />
      <div style={{
        position: "absolute",
        top: "15%",
        width: "100%",
        textAlign: "center",
      }}>
        <span style={{
          color: COLORS.text,
          fontSize: 48,
          fontWeight: 700,
          fontFamily: "'Microsoft YaHei', sans-serif",
        }}>
          LLM 四级级联
        </span>
      </div>
      <div style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        height: "100%",
        gap: gap,
      }}>
        {nodes.map((node, i) => {
          const nodeOpacity = interpolate(frame, [10 + i * 8, 25 + i * 8], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
          const isHighlight = node.name === "壁韧" && frame > 40;
          const pulseScale = isHighlight ? 1 + Math.sin(frame * 0.15) * 0.05 : 1;

          return (
            <div key={i} style={{ position: "relative" }}>
              <div style={{
                opacity: nodeOpacity,
                transform: `scale(${pulseScale})`,
                background: isHighlight ? `${node.color}33` : COLORS.cardBg,
                border: `2px solid ${isHighlight ? node.color : `${node.color}44`}`,
                borderRadius: 16,
                padding: "32px 24px",
                textAlign: "center",
                minWidth: nodeWidth,
                boxShadow: isHighlight ? `0 0 40px ${node.color}66` : `0 4px 16px rgba(0,0,0,0.3)`,
              }}>
                <span style={{
                  color: node.color,
                  fontSize: 32,
                  fontWeight: 700,
                  fontFamily: "'Microsoft YaHei', sans-serif",
                  display: "block",
                }}>
                  {node.name}
                </span>
                <span style={{
                  color: COLORS.textDim,
                  fontSize: 18,
                  fontFamily: "'Microsoft YaHei', sans-serif",
                  marginTop: 8,
                  display: "block",
                }}>
                  {node.role}
                </span>
              </div>
              {/* Arrow */}
              {i < nodes.length - 1 && (
                <div style={{
                  position: "absolute",
                  right: -gap,
                  top: "50%",
                  transform: "translateY(-50%)",
                  opacity: interpolate(frame, [20 + i * 8, 30 + i * 8], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
                }}>
                  <svg width={gap} height="20" viewBox={`0 0 ${gap} 20`}>
                    <line x1="0" y1="10" x2={gap - 10} y2="10" stroke={COLORS.accent} strokeWidth="2" strokeDasharray="4 4">
                      <animate attributeName="stroke-dashoffset" from={gap} to="0" dur="1s" repeatCount="indefinite" />
                    </line>
                    <polygon points={`${gap - 10},4 ${gap},10 ${gap - 10},16`} fill={COLORS.accent} />
                  </svg>
                </div>
              )}
            </div>
          );
        })}
      </div>
      {/* Bottom banner */}
      <div style={{
        position: "absolute",
        bottom: 120,
        width: "100%",
        textAlign: "center",
        opacity: interpolate(frame, [60, 80], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
      }}>
        <div style={{
          display: "inline-block",
          padding: "12px 32px",
          background: `${COLORS.warning}22`,
          border: `1px solid ${COLORS.warning}`,
          borderRadius: 8,
        }}>
          <span style={{ color: COLORS.warning, fontSize: 24, fontFamily: "'Microsoft YaHei', sans-serif" }}>
            无Key明确报错 · 不静默降级
          </span>
        </div>
      </div>
    </AbsoluteFill>
  );
};

// Shot 11: Deployment architecture
const ShotDeploy: React.FC<{ shot: Shot }> = ({ shot }) => {
  const frame = useCurrentFrame();
  const { opacity, transform } = useFadeTransition(frame, shot.durationInFrames, shot.transition);

  const services = [
    { name: "Nginx", port: "8088", status: "running" },
    { name: "FastAPI", port: "8090", status: "running" },
    { name: "Flask", port: "8082", status: "running" },
    { name: "MCP", port: "8765", status: "running" },
    { name: "PostgreSQL", port: "5432", status: "running" },
  ];

  const urlText = "http://171.111.219.204:8088";
  const typedChars = Math.floor(interpolate(frame, [20, 60], [0, urlText.length], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }));
  const cursorVisible = Math.floor(frame / 15) % 2 === 0;

  return (
    <AbsoluteFill style={{ opacity, transform }}>
      <GradientBg bg={shot.bg} />
      <div style={{
        position: "relative",
        zIndex: 10,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        height: "100%",
        gap: 40,
      }}>
        <span style={{
          color: COLORS.text,
          fontSize: 48,
          fontWeight: 700,
          fontFamily: "'Microsoft YaHei', sans-serif",
        }}>
          天翼云 ECS 公网部署
        </span>
        {/* URL typewriter */}
        <div style={{
          background: "rgba(0,0,0,0.4)",
          border: `1px solid ${COLORS.accent}`,
          borderRadius: 12,
          padding: "16px 32px",
        }}>
          <span style={{
            color: COLORS.accent,
            fontSize: 36,
            fontFamily: "'Courier New', monospace",
            fontWeight: 700,
          }}>
            {urlText.substring(0, typedChars)}
            {typedChars < urlText.length && cursorVisible && <span style={{ color: COLORS.accent }}>|</span>}
          </span>
        </div>
        {/* Service indicators */}
        <div style={{ display: "flex", gap: 20 }}>
          {services.map((svc, i) => {
            const lightOn = frame > 60 + i * 8;
            return (
              <div key={i} style={{
                background: COLORS.cardBg,
                border: `1px solid ${COLORS.cardBorder}`,
                borderRadius: 12,
                padding: "20px 24px",
                textAlign: "center",
                minWidth: 140,
              }}>
                <div style={{
                  width: 16,
                  height: 16,
                  borderRadius: "50%",
                  background: lightOn ? COLORS.success : "rgba(255,255,255,0.1)",
                  margin: "0 auto 12px",
                  boxShadow: lightOn ? `0 0 12px ${COLORS.success}` : "none",
                }} />
                <span style={{
                  color: COLORS.text,
                  fontSize: 22,
                  fontWeight: 600,
                  fontFamily: "'Microsoft YaHei', sans-serif",
                  display: "block",
                }}>
                  {svc.name}
                </span>
                <span style={{
                  color: COLORS.textDim,
                  fontSize: 16,
                  fontFamily: "'Microsoft YaHei', sans-serif",
                }}>
                  :{svc.port}
                </span>
              </div>
            );
          })}
        </div>
        <span style={{
          color: COLORS.textDim,
          fontSize: 20,
          fontFamily: "'Microsoft YaHei', sans-serif",
          opacity: interpolate(frame, [100, 120], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
        }}>
          systemd · Restart=always
        </span>
      </div>
    </AbsoluteFill>
  );
};

// Shot 12: Radar chart
const ShotRadar: React.FC<{ shot: Shot }> = ({ shot }) => {
  const frame = useCurrentFrame();
  const { opacity, transform } = useFadeTransition(frame, shot.durationInFrames, shot.transition);

  const dimensions = [
    { name: "创新性", score: 85, angle: -90 },
    { name: "商业模式", score: 78, angle: -18 },
    { name: "社会价值", score: 82, angle: 54 },
    { name: "应用成效", score: 80, angle: 126 },
    { name: "可孵化性", score: 85, angle: 198 },
  ];

  const centerX = 960;
  const centerY = 480;
  const maxRadius = 260;
  const drawProgress = interpolate(frame, [15, 80], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) });

  const getPoint = (angle: number, radius: number) => {
    const rad = (angle * Math.PI) / 180;
    return {
      x: centerX + radius * Math.cos(rad),
      y: centerY + radius * Math.sin(rad),
    };
  };

  // Build radar polygon
  const points = dimensions.map(d => {
    const r = (d.score / 100) * maxRadius * drawProgress;
    return getPoint(d.angle, r);
  });
  const polygonStr = points.map(p => `${p.x},${p.y}`).join(" ");

  return (
    <AbsoluteFill style={{ opacity, transform }}>
      <GradientBg bg={shot.bg} />
      <div style={{
        position: "absolute",
        top: 60,
        width: "100%",
        textAlign: "center",
      }}>
        <span style={{
          color: COLORS.text,
          fontSize: 44,
          fontWeight: 700,
          fontFamily: "'Microsoft YaHei', sans-serif",
        }}>
          五维评分
        </span>
      </div>
      {/* SVG Radar */}
      <svg width="1920" height="1080" style={{ position: "absolute", top: 0, left: 0 }}>
        {/* Grid circles */}
        {[0.2, 0.4, 0.6, 0.8, 1.0].map((ratio, i) => (
          <circle key={i} cx={centerX} cy={centerY} r={maxRadius * ratio} fill="none" stroke="rgba(255,255,255,0.1)" strokeWidth="1" />
        ))}
        {/* Axis lines */}
        {dimensions.map((d, i) => {
          const p = getPoint(d.angle, maxRadius);
          return <line key={i} x1={centerX} y1={centerY} x2={p.x} y2={p.y} stroke="rgba(255,255,255,0.1)" strokeWidth="1" />;
        })}
        {/* Data polygon */}
        {drawProgress > 0.1 && (
          <polygon points={polygonStr} fill={`${COLORS.accent}33`} stroke={COLORS.accent} strokeWidth="2" />
        )}
        {/* Data points */}
        {points.map((p, i) => (
          <g key={i}>
            <circle cx={p.x} cy={p.y} r="6" fill={COLORS.accent} />
            <text x={p.x} y={p.y - 16} fill={COLORS.text} fontSize="20" fontFamily="'Microsoft YaHei', sans-serif" textAnchor="middle">
              {dimensions[i].name}
            </text>
            <text x={p.x} y={p.y + 28} fill={COLORS.accent} fontSize="22" fontFamily="'Microsoft YaHei', sans-serif" fontWeight="700" textAnchor="middle">
              {dimensions[i].score}
            </text>
          </g>
        ))}
      </svg>
      {/* Total score */}
      <div style={{
        position: "absolute",
        bottom: 100,
        width: "100%",
        textAlign: "center",
        opacity: interpolate(frame, [80, 100], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
      }}>
        <span style={{
          color: COLORS.success,
          fontSize: 64,
          fontWeight: 800,
          fontFamily: "'Microsoft YaHei', sans-serif",
        }}>
          综合 82 分
        </span>
      </div>
    </AbsoluteFill>
  );
};

// Shot 13: CTA ending
const ShotCTA: React.FC<{ shot: Shot }> = ({ shot }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { opacity, transform } = useFadeTransition(frame, shot.durationInFrames, shot.transition);

  const titleScale = spring({
    frame,
    fps,
    config: { damping: 12, mass: 1, stiffness: 100 },
    durationInFrames: 30,
  });

  const subtitleOpacity = interpolate(frame, [25, 50], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const linksOpacity = interpolate(frame, [40, 65], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const ctaBlink = frame > 90 ? (Math.sin(frame * 0.2) > 0 ? 1 : 0.3) : 0;

  return (
    <AbsoluteFill style={{ opacity, transform, justifyContent: "center", alignItems: "center" }}>
      <GradientBg bg={shot.bg} />
      <div style={{
        transform: `scale(${titleScale})`,
        textAlign: "center",
        zIndex: 10,
      }}>
        <h1 style={{
          color: COLORS.text,
          fontSize: 100,
          fontWeight: 800,
          fontFamily: "'Microsoft YaHei', sans-serif",
          margin: 0,
          textShadow: `0 0 60px ${COLORS.primary}88`,
          letterSpacing: "0.1em",
        }}>
          息壤育智 · 一人成军
        </h1>
      </div>
      <div style={{
        position: "absolute",
        top: "58%",
        textAlign: "center",
        opacity: linksOpacity,
      }}>
        <div style={{ marginBottom: 16 }}>
          <span style={{ color: COLORS.accent, fontSize: 28, fontFamily: "'Courier New', monospace" }}>
            http://171.111.219.204:8088
          </span>
        </div>
        <div>
          <span style={{ color: COLORS.textDim, fontSize: 22, fontFamily: "'Courier New', monospace" }}>
            github.com/yigenfeng0707-netizen/chengjuntai-opc-xirang
          </span>
        </div>
      </div>
      <div style={{
        position: "absolute",
        bottom: 80,
        textAlign: "center",
        opacity: subtitleOpacity,
      }}>
        <span style={{
          color: COLORS.textDim,
          fontSize: 24,
          fontFamily: "'Microsoft YaHei', sans-serif",
        }}>
          感谢评委 · 欢迎体验
        </span>
      </div>
      <div style={{
        position: "absolute",
        bottom: 150,
        textAlign: "center",
        opacity: ctaBlink,
      }}>
        <span style={{
          color: COLORS.warning,
          fontSize: 28,
          fontWeight: 700,
          fontFamily: "'Microsoft YaHei', sans-serif",
        }}>
          请点评委六十秒体验
        </span>
      </div>
    </AbsoluteFill>
  );
};

// ==================== Shot Router (route by id for reliability) ====================
const ShotRenderer: React.FC<{ shot: Shot }> = ({ shot }) => {
  switch (shot.id) {
    case "shot-01":
      return <ShotCover shot={shot} />;
    case "shot-02":
      return <ShotBullets shot={shot} />;
    case "shot-03":
      return <ShotSection shot={shot} />;
    case "shot-04":
      return <ShotLogin shot={shot} />;
    case "shot-05":
      return <ShotDashboard shot={shot} />;
    case "shot-06":
    case "shot-07":
    case "shot-08":
      return <ShotCaptions shot={shot} />;
    case "shot-09":
      return <ShotMetrics shot={shot} />;
    case "shot-10":
      return <ShotLLMCascade shot={shot} />;
    case "shot-11":
      return <ShotDeploy shot={shot} />;
    case "shot-12":
      return <ShotRadar shot={shot} />;
    case "shot-13":
      return <ShotCTA shot={shot} />;
    default:
      return <ShotCover shot={shot} />;
  }
};

// ==================== Root Composition ====================
export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="DemoVideo"
        component={DemoVideo}
        durationInFrames={data.totalFrames}
        fps={data.fps}
        width={data.width}
        height={data.height}
      />
    </>
  );
};

const DemoVideo: React.FC = () => {
  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.bg }}>
      {data.shots.map((shot, index) => (
        <Sequence
          key={shot.id}
          from={shot.startFrame}
          durationInFrames={shot.durationInFrames}
          name={shot.id}
        >
          <ShotRenderer shot={shot} />
          <Audio src={staticFile(shot.audio)} />
          <SubtitleBar narration={shot.narration} durationInFrames={shot.durationInFrames} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};

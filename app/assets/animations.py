import random

__all__ = [
    "clear_html",
    "rainy_html",
    "snowy_html",
    "cloudy_html",
    "windy_html",
    "stormy_html",
    "hot_html",
    "cold_html",
]


def clear_html() -> str:
    return """
    <style>
    .weather-container.clear-container {
        position: fixed; top:0; left:0;
        width:100vw; height:100vh;
        background: linear-gradient(to bottom, #50C9CE, #E0F7FA);
        pointer-events: none; z-index: -1;
    }
    .clear-sun {
        position: absolute; top:10%; right:10%;
        width: 300px; height: 300px;
        background: radial-gradient(circle at center,
                    rgba(255,255,240,1) 0%,
                    rgba(255,240,200,0.6) 40%,
                    transparent 70%);
        border-radius: 50%;
        filter: blur(40px) brightness(2);
        animation: sunPulse 6s ease-in-out infinite;
    }
    .clear-flare1 {
        position: absolute; top:10%; right:10%;
        width: 500px; height: 500px;
        background: radial-gradient(circle at center,
                    rgba(255,255,240,0.3) 0%, transparent 80%);
        border-radius: 50%; filter: blur(80px);
        animation: flarePulse 6s ease-in-out infinite;
    }
    .clear-flare2 {
        position: absolute; top:10%; right:10%;
        width: 700px; height: 700px;
        background: radial-gradient(circle at center,
                    rgba(255,255,240,0.15) 0%, transparent 90%);
        border-radius: 50%; filter: blur(120px);
        animation: flarePulse 6s ease-in-out infinite reverse;
    }
    @keyframes sunPulse {
        0%,100% { transform: scale(1); opacity:0.8; }
        50%     { transform: scale(1.2); opacity:1; }
    }
    @keyframes flarePulse {
        0%,100% { opacity:0.3; }
        50%     { opacity:0.6; }
    }
    </style>
    <div class="weather-container clear-container">
    <div class="clear-sun"></div>
    <div class="clear-flare1"></div>
    <div class="clear-flare2"></div>
    </div>
    """


def rainy_html() -> str:
    drops = "".join(
        f'<div class="drop" style="left:{random.uniform(0,100):.1f}%; '
        f'animation-duration:{random.uniform(0.7,1.4):.2f}s; '
        f'animation-delay:{random.uniform(-1.5,0):.2f}s;"></div>'
        for _ in range(80)
    )
    return f"""
    <style>
    .weather-container.rain-container {{
        position:fixed; top:0; left:0;
        width:100vw; height:100vh;
        background: radial-gradient(circle at top, #283048, #859398);
        pointer-events:none; z-index:-1;
    }}
    .drop {{
        position:absolute; bottom:100%;
        width:2px; height:15px;
        background: rgba(255,255,255,0.8);
        box-shadow:0 0 2px rgba(255,255,255,0.5);
        animation: fall 1s linear infinite;
    }}
    @keyframes fall {{
        0%   {{ transform: translateY(0) rotate(2deg); opacity:1; }}
        70%  {{ opacity:0.7; }}
        100% {{ transform: translateY(110vh) rotate(5deg); opacity:0; }}
    }}
    </style>
    <div class="weather-container rain-container">
    {drops}
    </div>
    """

def snowy_html() -> str:
    flakes = "".join(
        f'<div class="flake" style="left:{random.uniform(0,100):.1f}%; '
        f'animation-duration:{random.uniform(4,8):.1f}s; '
        f'animation-delay:{random.uniform(-8,0):.1f}s; '
        f'width:{random.uniform(8,16):.1f}px; height:{random.uniform(8,16):.1f}px;"></div>'
        for _ in range(100)
    )
    return f"""
    <style>
    .weather-container.snow-container {{
        position:fixed; top:0; left:0;
        width:100vw; height:100vh;
        background: linear-gradient(to bottom, #1e3c72, #2a5298);
        pointer-events:none; z-index:-1;
    }}
    .flake {{
        position:absolute; top:-10%;
        background: rgba(255,255,255,0.9);
        border-radius:50%; opacity:0.8;
        animation: drift linear infinite;
    }}
    @keyframes drift {{
        to {{ transform: translateY(110vh) translateX(10vw) rotate(360deg); }}
    }}
    .snow-container::after {{
        content:''; position:absolute; top:0; left:0;
        width:100%; height:100%;
        background: rgba(255,255,255,0.2);
        backdrop-filter: blur(4px);
    }}
    </style>
    <div class="weather-container snow-container">
    {flakes}
    </div>
    """


def cloudy_html() -> str:
    clouds = "".join(
        f'<div class="cloud" style="top:{random.uniform(10,70):.1f}%; '
        f'left:{-300+random.uniform(0,100):.1f}px; '
        f'width:{random.uniform(150,300):.0f}px; height:{random.uniform(60,100):.0f}px; '
        f'animation-duration:{random.uniform(30,60):.0f}s; '
        f'animation-delay:{random.uniform(-30,0):.0f}s;"></div>'
        for _ in range(15)
    )
    return f"""
    <style>
    .weather-container.cloud-container {{
        position:fixed; top:0; left:0;
        width:100vw; height:100vh;
        background: linear-gradient(to bottom, #cfd9df, #e2ebf0);
        pointer-events:none; z-index:-1;
    }}
    .cloud {{
        position:absolute; background: rgba(255,255,255,0.85);
        border-radius:50px; filter: blur(5px);
        animation: moveCloud linear infinite;
    }}
    @keyframes moveCloud {{
        from {{ transform: translateX(0); }}
        to   {{ transform: translateX(125vw); }}
    }}
    </style>
    <div class="weather-container cloud-container">
    {clouds}
    </div>
    """


def windy_html() -> str:
    lines = "".join(
        f'<div class="wind-line" style="top:{random.uniform(0,100):.1f}%; '
        f'animation-duration:{random.uniform(2,4):.1f}s;"></div>'
        for _ in range(20)
    )
    return f"""
    <style>
    .weather-container.windy-container {{
        position:fixed; top:0; left:0;
        width:100vw; height:100vh;
        background: #a3c4f3;
        pointer-events:none; z-index:-1;
    }}
    .wind-line {{
        position:absolute; left:100%;
        width:200px; height:3px;
        background: rgba(255,255,255,0.6);
        animation: windLine 5s linear infinite;
    }}
    @keyframes windLine {{
        to {{ transform: translateX(-200vw); }}
    }}
    </style>
    <div class="weather-container windy-container">
    {lines}
    </div>
    """


def stormy_html() -> str:
    drops = "".join(
        f'<div class="drop" style="left:{random.uniform(0,100):.1f}%;'
        f'animation-duration:{random.uniform(0.5,1):.2f}s; animation-delay:{random.uniform(-1,0):.2f}s;"></div>'
        for _ in range(60)
    )
    bolts = "".join(
        f'<div class="bolt" style="left:{random.uniform(10,90):.1f}%; '
        f'--angle:{random.uniform(-30,30):.1f}deg; '
        f'--dur:{random.uniform(12,20):.2f}s; '
        f'--delay:{random.uniform(0,6):.1f}s; '
        f'width:{random.uniform(40,80):.0f}px; height:{random.uniform(240,420):.0f}px;">'
        '<svg viewBox="0 0 20 60" width="100%" height="100%" preserveAspectRatio="none">'
            '<polygon points="10,0 20,30 12,30 18,60 0,25 8,25" fill="yellow"/>'
        '</svg>'
        '</div>'
        for _ in range(7)
    )
    return f"""
    <style>
    .weather-container.storm-container {{
        position:fixed; top:0; left:0;
        width:100vw; height:100vh;
        background:#111;
        pointer-events:none; z-index:-1;
    }}
    .drop {{
        position:absolute; bottom:100%;
        width:2px; height:15px;
        background:rgba(200,200,200,0.8);
        animation: fall 1s linear infinite;
    }}
    @keyframes fall {{
        to {{ transform: translateY(110vh) rotate(5deg); opacity:0; }}
    }}
    .bolt {{
        position:absolute; top:-50%;
        transform-origin:top center;
        animation: boltFall var(--dur) ease-in-out var(--delay) infinite;
    }}
    @keyframes boltFall {{
        0%   {{ transform: rotate(var(--angle)) translateY(0); opacity:1; }}
        95%  {{ transform: rotate(var(--angle)) translateY(200vh); opacity:1; }}
        100% {{ opacity:0; }}
    }}
    .flash {{
        position:absolute; top:0; left:0;
        width:100%; height:100%; background:white;
        animation: lightningFlash 6s ease-in-out infinite;
    }}
    @keyframes lightningFlash {{
        0%,80%,100% {{ opacity:0; }}
        82%,86%      {{ opacity:1; }}
    }}
    </style>
    <div class="weather-container storm-container">
    {drops}
    <div class="flash"></div>
    {bolts}
    </div>
    """


def hot_html() -> str:
    waves = "".join(
        f'<div class="wave" style="left:{random.uniform(10,90):.1f}%; '
        f'bottom:{random.uniform(5,20):.1f}%; '
        f'width:{random.uniform(100,300):.0f}px; height:{random.uniform(4,8):.0f}px; '
        f'animation-duration:{random.uniform(3,5):.2f}s; animation-delay:{random.uniform(-3,0):.2f}s;"></div>'
        for _ in range(12)
    )
    return f"""
    <style>
    .weather-container.hot-container {{
        position:fixed; top:0; left:0;
        width:100vw; height:100vh;
        background: linear-gradient(to bottom, #ffcccc, #ff9999);
        pointer-events:none; z-index:-1;
    }}
    .sun {{
        position:absolute; top:10%; left:50%;
        width:250px; height:250px;
        background: radial-gradient(circle at center,
                    rgba(255,240,200,0.7) 0%, rgba(255,200,0,0.3) 60%);
        border-radius:50%; filter: blur(20px);
        animation: sunGlow 6s ease-in-out infinite;
        transform: translateX(-50%);
    }}
    @keyframes sunGlow {{
        0%,100% {{ transform: translateX(-50%) scale(1); opacity:0.6; }}
        50%    {{ transform: translateX(-50%) scale(1.1); opacity:0.8; }}
    }}
    .wave {{
        position:absolute; border:2px solid rgba(255,255,255,0.3);
        border-radius:50%; opacity:0;
        animation: waveRise 4s ease-in-out infinite;
    }}
    @keyframes waveRise {{
        0%,100% {{ transform: scale(1); opacity:0; }}  
        50%     {{ transform: scale(1.1); opacity:0.3; }}
    }}
    </style>
    <div class="weather-container hot-container">
    <div class="sun"></div>
    {waves}
    </div>
    """


def cold_html() -> str:
    flakes = "".join(
        f'<div class="snowflake" style="left:{random.uniform(0,100):.1f}%; '
        f'animation-duration:{random.uniform(4,8):.1f}s; animation-delay:{random.uniform(-8,0):.1f}s; '
        f'width:{random.uniform(6,12):.1f}px; height:{random.uniform(6,12):.1f}px;"></div>'
        for _ in range(80)
    )
    windlines = "".join(
        f'<div class="wind-line" style="top:{random.uniform(0,100):.1f}%; '
        f'animation-duration:{random.uniform(3,6):.1f}s;"></div>'
        for _ in range(20)
    )
    return f"""
    <style>
    .weather-container.cold-container {{
        position:fixed; top:0; left:0;
        width:100vw; height:100vh;
        background: linear-gradient(to bottom, #0f2027, #2c5364);
        pointer-events:none; z-index:-1;
    }}
    .snowflake {{
        position:absolute; top:-10%;
        background: rgba(255,255,255,0.9);
        border-radius:50%; opacity:0.8;
        animation: snowFall linear infinite;
    }}
    @keyframes snowFall {{
        to {{ transform: translateY(110vh) rotate(360deg); opacity:0; }}
    }}
    .wind-line {{
        position:absolute; left:100%;
        width:200px; height:3px;
        background: rgba(255,255,255,0.5);
        animation: windBlast linear infinite;
    }}
    @keyframes windBlast {{
        to {{ transform: translateX(-200vw); }}
    }}
    .cold-container::after {{
        content:''; position:absolute; top:0; left:0;
        width:100%; height:100%;
        background: rgba(200,230,255,0.2);
        backdrop-filter: blur(4px);
    }}
    </style>
    <div class="weather-container cold-container">
    {windlines}
    {flakes}
    </div>
    """
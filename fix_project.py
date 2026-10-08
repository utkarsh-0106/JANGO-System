from pathlib import Path
import re

root = Path('/mnt/data/jango-fix-work')
src = root / 'frontend' / 'src'

# ---------------- Theme: Gold/Silver only ----------------
(src/'context'/'ThemeContext.jsx').write_text('''import { createContext, useContext, useEffect } from "react";\n\nconst ThemeContext = createContext(null);\n\nexport function ThemeProvider({ children }) {\n  useEffect(() => {\n    document.documentElement.dataset.theme = "gold-silver";\n    window.localStorage.setItem("jango-theme", "gold-silver");\n  }, []);\n\n  const value = {\n    theme: "gold-silver",\n    isGoldSilver: true,\n    toggleTheme: () => {},\n  };\n\n  return (\n    <ThemeContext.Provider value={value}>\n      {children}\n    </ThemeContext.Provider>\n  );\n}\n\nexport function useTheme() {\n  const context = useContext(ThemeContext);\n  if (!context) {\n    throw new Error("useTheme must be used inside ThemeProvider");\n  }\n  return context;\n}\n''')

# Remove ThemeToggle imports and JSX usages everywhere.
for p in src.rglob('*'):
    if not p.is_file() or p.suffix not in {'.js','.jsx','.ts','.tsx'}:
        continue
    if p.name == 'ThemeToggle.jsx':
        continue
    s = p.read_text()
    s = re.sub(r'import\s+ThemeToggle\s+from\s+["\'][^"\']*ThemeToggle["\'];?\s*', '', s)
    s = re.sub(r'\s*<ThemeToggle(?:\s+compact)?\s*/>\s*', '\n', s)
    p.write_text(s)

# Remove toggle component.
toggle = src/'components'/'ThemeToggle.jsx'
if toggle.exists(): toggle.unlink()

# RAG response must expose usage to the Chat page.
rag_schema = root/'backend/app/schemas/rag.py'
rag_schema.write_text('''from pydantic import BaseModel\nfrom typing import List, Optional\n\n\nclass RagRequest(BaseModel):\n    question: str\n    top_k: Optional[int] = 5\n\n\nclass RagResponse(BaseModel):\n    answer: str\n    sources: List[dict]\n    usage: Optional[dict] = None\n''')

# Make RAG no-result responses explicit about usage.
rag_service = root/'backend/app/services/rag.py'
s = rag_service.read_text()
s = s.replace('''        return RagResponse(\n            answer="I don't know based on the uploaded documents.",\n            sources=[],\n        )''','''        return RagResponse(\n            answer="I don't know based on the uploaded documents.",\n            sources=[],\n            usage=None,\n        )''')
rag_service.write_text(s)

# Ensure Chat has a clear empty-state error and stable response handling.
chat = src/'pages'/'Chat.jsx'
s = chat.read_text()
s = s.replace('''      setMessages((current) => [\n        ...current,\n        {\n          role: "assistant",\n          content: response.data.answer,\n          sources: response.data.sources || [],\n          usage: response.data.usage || null,\n        },\n      ]);''','''      const data = response.data || {};\n      setMessages((current) => [\n        ...current,\n        {\n          role: "assistant",\n          content: data.answer || "Jango returned an empty answer.",\n          sources: Array.isArray(data.sources) ? data.sources : [],\n          usage: data.usage || null,\n        },\n      ]);''')
chat.write_text(s)

# Analytics: remove now-nonexistent theme control and make API errors actionable.
analytics = src/'pages'/'Analytics.jsx'
s = analytics.read_text()
s = s.replace('''    } catch (err) {\n      setError(err.response?.data?.detail || "Unable to load AI usage analytics.");''','''    } catch (err) {\n      const status = err.response?.status;\n      const detail = err.response?.data?.detail;\n      setError(\n        status === 401\n          ? "Your session has expired. Please log in again."\n          : detail || "Unable to load AI usage analytics. Make sure the JANGO backend is running."\n      );''')
analytics.write_text(s)

# Make sidebar Documents link go to dashboard section instead of a dead standalone href.
sidebar = src/'components'/'Sidebar.jsx'
s = sidebar.read_text().replace('''        <a\n          href="#documents"\n          className="sidebar-link"\n        >''','''        <Link\n          to="/dashboard#documents"\n          className="sidebar-link"\n        >''').replace('''        </a>\n\n        <Link\n          to="/analytics"''','''        </Link>\n\n        <Link\n          to="/analytics"''')
sidebar.write_text(s)

# ---------------- CSS: eliminate Purple variables and make root Gold/Silver ----------------
css_path = src/'App.css'
css = css_path.read_text()
replacements = {
    '--accent-rgb: 139 92 246;':'--accent-rgb: 212 175 55;',
    '--accent-deep-rgb: 124 58 237;':'--accent-deep-rgb: 184 134 11;',
    '--accent-light-rgb: 167 139 250;':'--accent-light-rgb: 247 215 116;',
    '--accent-secondary-rgb: 79 70 229;':'--accent-secondary-rgb: 201 206 214;',
    '--accent-cool-rgb: 34 211 238;':'--accent-cool-rgb: 192 198 208;',
    '--accent-cool-light-rgb: 103 232 249;':'--accent-cool-light-rgb: 229 231 235;',
    '--accent: #8b5cf6;':'--accent: #d4af37;',
    '--accent-deep: #7c3aed;':'--accent-deep: #b8860b;',
    '--accent-secondary: #4f46e5;':'--accent-secondary: #c9ced6;',
    '--accent-light: #b39aff;':'--accent-light: #f7d774;',
    '--accent-light-2: #a78bfa;':'--accent-light-2: #e5e7eb;',
    '--accent-cool: #22d3ee;':'--accent-cool: #c0c6d0;',
    '--accent-cool-light: #67e8f9;':'--accent-cool-light: #f1f3f5;',
    '--accent-muted: #7771b7;':'--accent-muted: #9f8a42;',
    '--bg: #05060b;':'--bg: #040404;',
    '--bg-2: #080a12;':'--bg-2: #090909;',
    '--surface: rgba(15, 17, 28, 0.72);':'--surface: rgba(18, 18, 18, 0.78);',
    '--surface-strong: rgba(18, 20, 34, 0.9);':'--surface-strong: rgba(20, 20, 20, 0.94);',
    '--surface-soft: rgba(255, 255, 255, 0.035);':'--surface-soft: rgba(255, 255, 255, 0.04);',
    '--border: rgba(255, 255, 255, 0.085);':'--border: rgba(255, 255, 255, 0.10);',
    '--text: #f8f8fc;':'--text: #f5f5f5;',
    '--text-soft: #c4c7d5;':'--text-soft: #d1d5db;',
    '--text-muted: #7d8197;':'--text-muted: #8f939a;',
}
for a,b in replacements.items(): css = css.replace(a,b)
css = css.replace('  --purple: var(--accent);\n  --purple-light: var(--accent-light);\n  --cyan: var(--accent-cool);\n','  --gold: var(--accent);\n  --silver: var(--accent-secondary);\n  --cyan: var(--accent-cool);\n')
css = css.replace('var(--purple-light)', 'var(--accent-light)')
css = css.replace('.stat-purple', '.stat-gold')
css = css.replace('JANGO THEME SYSTEM — PURPLE / GOLD + SILVER','JANGO THEME SYSTEM — GOLD + SILVER ONLY')
# Remove the theme toggle style section because the toggle no longer exists.
css = re.sub(r'/\* Theme palette control \*/.*?(?=/\* =========================================================\n   AI USAGE & COST ANALYTICS)', '', css, flags=re.S)
# Remove the obsolete purple-specific selector from the old theme block if any remain.
css = css.replace('html[data-theme="gold-silver"] .theme-toggle,\n','')
css = css.replace('html[data-theme="gold-silver"] .theme-toggle:hover {\n  border-color: rgb(var(--accent-rgb) / 0.55);\n  box-shadow: 0 0 28px rgb(var(--accent-rgb) / 0.14);\n}\n\nhtml[data-theme="gold-silver"] .theme-toggle-icon {\n  color: var(--accent-light);\n}\n\n','')
css_path.write_text(css)

# Delete old backup CSS and JSX backups from source so they don't get mistaken for active code.
for name in ['App.css.backup']:
    p=src/name
    if p.exists(): p.unlink()
for name in ['Chat.jsx.backup','Dashboard.jsx.backup']:
    p=src/'pages'/name
    if p.exists(): p.unlink()

print('Patched JANGO.')

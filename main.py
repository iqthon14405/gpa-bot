import sys
import subprocess

# 🛠️ تثبيت تلقائي لأي مكتبة ناقصة في المنصة لضمان عدم توقف البوت
REQUIRED_LIBRARIES = {
    "telegram": "python-telegram-bot==20.8",
    "reportlab": "reportlab",
    "arabic_reshaper": "arabic-reshaper",
    "bidi": "python-bidi"
}

for module_name, pip_name in REQUIRED_LIBRARIES.items():
    try:
        __import__(module_name)
    except ImportError:
        print(f"📦 جاري تثبيت المكتبة المفقودة تلقائياً: {pip_name} ...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", pip_name])

# ============================================
# استدعاء الملاحق والملفات الأساسية
# ============================================
import logging
import sqlite3
import json
import os
from datetime import datetime
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus.flowables import HRFlowable

import arabic_reshaper
from bidi.algorithm import get_display

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, ConversationHandler, filters
from telegram.constants import ParseMode

# ============================================
# الإعدادات الأساسية وتوكين البوت المباشر
# ============================================
API_TOKEN = "8291484744:AAHAyOAMx2dvAd6gNaUk5KCaC1yWOiH4HmM" 
ADMIN_USER_ID = 5856082274          
DEVELOPER_NAME = "تطوير وبرمجة / بكيل الراعي"

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

def ar(text):
    if not text: return ""
    reshaped = arabic_reshaper.reshape(str(text))
    return get_display(reshaped)

# ============================================
# إعداد قواعد البيانات والمناهج
# ============================================
def init_db():
    conn = sqlite3.connect('gpa_bot.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, last_name TEXT, joined_date TEXT, last_active TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS activity_log (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT, action TEXT, details TEXT, timestamp TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS saved_progress (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, department TEXT, level INTEGER, calculation_type TEXT, saved_data TEXT, saved_date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS student_records (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT, department TEXT, level INTEGER, calculation_type TEXT, result_data TEXT, cumulative_gpa REAL, timestamp TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS curriculum (id INTEGER PRIMARY KEY AUTOINCREMENT, department TEXT, level INTEGER, term INTEGER, subject_name TEXT, credit_hours REAL, is_active INTEGER DEFAULT 1)''')
    conn.commit()
    conn.close()

def log_activity(user_id, username, action, details=""):
    try:
        conn = sqlite3.connect('gpa_bot.db')
        c = conn.cursor()
        c.execute("INSERT INTO activity_log (user_id, username, action, details, timestamp) VALUES (?, ?, ?, ?, ?)", (user_id, username, action, details, datetime.now().isoformat()))
        conn.commit()
        conn.close()
    except Exception as e: logger.error(f"Error logging activity: {e}")

def log_or_update_user(user_id, username, first_name, last_name=""):
    try:
        conn = sqlite3.connect('gpa_bot.db')
        c = conn.cursor()
        now = datetime.now().isoformat()
        c.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        if c.fetchone():
            c.execute("UPDATE users SET username=?, last_active=? WHERE user_id=?", (username, now, user_id))
        else:
            c.execute("INSERT INTO users (user_id, username, first_name, last_name, joined_date, last_active) VALUES (?, ?, ?, ?, ?, ?)", (user_id, username, first_name, last_name, now, now))
        conn.commit()
        conn.close()
    except Exception as e: logger.error(f"Error updating user: {e}")

# المنهج الدراسي لكليات العلوم الإدارية بجامعة إب
DEFAULT_CURRICULUM = {
    "قسم المحاسبة": {
        1: {
            1: [("محاسبة مالية 1", 3), ("مبادئ إدارة أعمال 1", 2), ("مبادئ اقتصاد جزئي", 2), ("رياضة بحتة 1", 3), ("لغة إنجليزية 101", 3), ("لغة عربية 101", 3), ("ثقافة وطنية", 3)],
            2: [("محاسبة مالية 2", 3), ("مبادئ اقتصاد كلي", 3), ("مبادئ إدارة أعمال 2", 2), ("نظام الحكم في اليمن", 2), ("لغة عربية 102", 3), ("لغة إنجليزية 102", 3), ("ثقافة إسلامية", 3), ("الصراع العربي الصهيوني", 3)]
        },
        2: {
            1: [("محاسبة متوسطة 1", 3), ("محاسبة شركات أشخاص", 3), ("مبادئ إحصاء", 3), ("مراسلات تجارية بالإنجليزية", 3), ("نقود وبنوك", 3), ("قانون تجاري", 3)],
            2: [("محاسبة متوسطة 2", 3), ("محاسبة شركات أموال", 3), ("إحصاء تطبيقي", 3), ("محاسبة منشآت مالية", 3), ("اقتصاديات مالية عامة", 3), ("قانون عمل وتشريعات تجارية", 3)]
        },
        3: {
            1: [("محاسبة تكاليف 1", 4), ("محاسبة حكومية وقومية", 4), ("محاسبة ضريبية 1", 3), ("إدارة مالية 1", 3), ("إدارة إنتاج وعمليات", 3), ("بحوث عمليات", 3)],
            2: [("محاسبة تكاليف 2", 4), ("محاسبة شركات عامة ومختلطة", 4), ("محاسبة ضريبية 2", 3), ("تحليل قوائم مالية", 3), ("محاسبة نفط", 4), ("مالية عامة", 3)]
        },
        4: {
            1: [("محاسبة إدارية 1", 4), ("مراجعة وحسابات 1", 4), ("نظم معلومات محاسبية", 3), ("دراسات محاسبية خاصة", 4), ("محاسبة مؤسسات مالية", 3), ("محاسبة دولية", 3)],
            2: [("محاسبة إدارية 2", 4), ("مراجعة وحسابات 2", 3), ("مشاكل محاسبية معاصرة / تكاليف 3", 4), ("نظرية المحاسبة", 3), ("قراءات محاسبية باللغة الإنجليزية", 2), ("بحث التخرج", 3)]
        }
    },
    "قسم العلوم المالية والمصرفية": {
        1: {
            1: [("محاسبة مالية (أ)", 3), ("مبادئ إدارة أعمال (أ)", 2), ("مبادئ الاقتصاد الجزئي (أ)", 2), ("الرياضة البحتة (أ)", 3), ("اللغة الإنجليزية (101)", 3), ("اللغة العربية (101)", 3), ("ثقافة وطنية", 3)],
            2: [("محاسبة مالية (ب)", 3), ("مبادئ إدارة أعمال (ب)", 2), ("مبادئ الاقتصاد الكلي", 2), ("نظام حكم", 3), ("اللغة العربية (102)", 3), ("اللغة الإنجليزية (102)", 3), ("ثقافة إسلامية", 3), ("الصراع العربي والصهيوني", 3)]
        },
        2: {
            1: [("إحصاء (1)", 3), ("محاسبة شركات أشخاص", 4), ("رياضة مالية", 3), ("نقود وبنوك", 3), ("مبادئ التسويق", 3), ("مناهج البحث العلمي", 2), ("حاسوب آلي (أ)", 3)],
            2: [("مبادئ الاستثمار", 4), ("إدارة مصارف", 3), ("محاسبة شركات أموال", 3), ("رياضة بحتة (ب)", 3), ("تنمية واقتصاد وتخطيط", 3), ("مراسلات تجارية", 3), ("حاسوب آلي (ب)", 3), ("قانون تجاري", 2)]
        },
        3: {
            1: [("التجارة الدولية", 3), ("بحوث عمليات", 3), ("إدارة استثمار", 4), ("مصطلحات مالية", 2), ("إدارة مالية", 3), ("بنوك إسلامية", 3)],
            2: [("تحليل مالي", 3), ("إدارة خطر وتأمين", 3), ("مالية عامة", 3), ("عمليات مصرفية محلية", 3), ("اقتصاد قياسي", 4), ("تشريعات مالية ومصرفية", 3)]
        },
        4: {
            1: [("التسويق المصرفي", 3), ("إدارة المنشآت المالية", 3), ("دراسة الجدوى وتقييم المشروعات", 3), ("محاسبة المنشآت المالية", 3), ("العمليات المصرفية الدولية", 3), ("نظم المعلومات المصرفية", 3)],
            2: [("أسواق مالية", 3), ("إدارة مخاطر مالية", 3), ("قضايا مصرفية معاصرة", 3), ("إدارة الائتمان", 3), ("تمويل دولي", 3), ("حلقة بحث", 3)]
        }
    },
    "قسم الإدارة العامة": {
        1: {
            1: [("محاسبة مالية (1)", 3), ("مبادئ الاقتصاد الجزئي", 2), ("مبادئ إدارة أعمال", 2), ("الرياضة البحتة (1)", 3), ("اللغة الإنجليزية (101)", 3), ("اللغة العربية (101)", 3), ("مبادئ العلوم السياسية", 3), ("ثقافة وطنية", 3)],
            2: [("محاسبة مالية (2)", 3), ("مبادئ الاقتصاد الكلي", 2), ("نظام الحكم في اليمن", 3), ("اللغة العربية (102)", 3), ("ثقافة إسلامية", 3), ("اللغة الإنجليزية (102)", 3), ("الصراع العربي الإسرائيلي", 3)]
        },
        2: {
            1: [("مبادئ قانون", 2), ("مبادئ إدارة عامة", 3), ("إدارة الموارد البشرية", 3), ("مبادئ إحصاء (1)", 3), ("مناهج البحث العلمي", 2), ("تتطبيقات الحاسوب في الإدارة", 3)],
            2: [("قانون تجاري", 2), ("إدارة محلية", 3), ("تخطيط وتنمية", 3), ("مراسلات إدارية", 3), ("حاسب آلي (ب)", 3), ("قانون إداري", 2), ("سياسات عامة", 3)]
        },
        3: {
            1: [("إدارة مالية", 3), ("تنمية إدارية", 3), ("سلوك تنظيمي", 3), ("بحوث عمليات", 3), ("محاسبة حكومية", 4), ("محاسبة ضريبية", 3), ("مقدمة في الخدمة الدبلوماسية", 3)],
            2: [("محاسبة في وحدات الحكم المحلي", 4), ("إدارة مالية في السلطة المحلية", 3), ("قضايا إدارية معاصرة", 3), ("إدارة استراتيجية", 3), ("مالية عامة", 3), ("إدارة مواد", 3), ("التدريب العملي", 3)]
        },
        4: {
            1: [("محاسبة إدارية", 4), ("علاقات عامة", 3), ("رقابة عامة", 3), ("دراسة جدوى", 3), ("حكومة إلكترونية", 3), ("إدارة بيئة", 3)],
            2: [("نظم معلومات", 3), ("المناقصات والمزايدات", 3), ("إدارة الأزمات", 3), ("إدارة وتقويم المشروعات", 3), ("القيادات الإدارية واتخاذ القرار", 3), ("بحث التخرج", 3)]
        }
    },
    "قسم إدارة الأعمال": {
        1: {
            1: [("محاسبة مالية (أ)", 3), ("اقتصاد جزئي", 2), ("إدارة أعمال (أ)", 2), ("الرياضة البحتة أ", 3), ("اللغة الإنجليزية 101", 3), ("اللغة العربية 101", 3), ("ثقافة وطنية", 3)],
            2: [("محاسبة مالية (ب)", 3), ("اقتصاد كلي", 2), ("إدارة أعمال (ب)", 2), ("نظام حكم", 3), ("اللغة العربية 102", 3), ("ثقافة إسلامية", 3), ("اللغة الإنجليزية 102", 3), ("صراع عربي إسرائيلي", 3)]
        },
        2: {
            1: [("إدارة موارد بشرية (1)", 3), ("شركات أشخاص", 4), ("مبادئ تسويق", 3), ("حاسب (أ)", 3), ("مناهج بحث", 2), ("قراءات إدارية", 3), ("إحصاء (1)", 3)],
            2: [("استراتيجيات تسويق", 3), ("إدارة عامة", 2), ("إدارة موارد بشرية (2)", 3), ("نظرية منظمة", 3), ("شركات أموال", 4), ("إحصاء (2)", 3), ("قانون تجاري", 2), ("حاسب (ب)", 3)]
        },
        3: {
            1: [("محاسبة تكاليف (أ)", 4), ("بحوث عمليات (1)", 3), ("إدارة منشآت", 3), ("اقتصاد إداري", 3), ("إدارة مالية (1)", 3), ("سلوك تنظيمي", 3)],
            2: [("محاسبة تكاليف (ب)", 4), ("إدارة المواد", 3), ("إدارة خطر وتأمين", 3), ("إدارة استراتيجية", 3), ("إدارة مالية (2)", 3), ("بحوث عمليات (2)", 3)]
        },
        4: {
            1: [("إدارة الإنتاج والعمليات (1)", 3), ("إدارة أعمال معاصرة E", 3), ("الرقابة الإدارية وتقييم الأداء", 3), ("إدارة الأعمال الدولية", 3), ("محاسبة إدارية (1)", 4), ("دراسة الجدوى وتقييم المشروعات", 3)],
            2: [("إدارة الإنتاج والعمليات (2)", 3), ("نظم المعلومات الإدارية", 3), ("إدارة الجودة الشاملة", 2), ("إدارة المصارف", 3), ("أعمال إلكترونية", 3), ("بحث التخرج", 3)]
        }
    }
}

def load_curriculum_from_db():
    conn = sqlite3.connect('gpa_bot.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM curriculum")
    if c.fetchone()[0] == 0:
        for dept, levels in DEFAULT_CURRICULUM.items():
            for level, terms in levels.items():
                for term, subjects in terms.items():
                    for subj_name, credit in subjects:
                        c.execute("INSERT INTO curriculum (department, level, term, subject_name, credit_hours, is_active) VALUES (?, ?, ?, ?, ?, 1)", (dept, level, term, subj_name, credit))
        conn.commit()
    curriculum = {}
    c.execute("SELECT department, level, term, subject_name, credit_hours FROM curriculum WHERE is_active=1 ORDER BY department, level, term, id")
    for row in c.fetchall():
        dept, level, term, subj_name, credit = row
        if dept not in curriculum: curriculum[dept] = {}
        if level not in curriculum[dept]: curriculum[dept][level] = {}
        if term not in curriculum[dept][level]: curriculum[dept][level][term] = []
        curriculum[dept][level][term].append((subj_name, credit))
    conn.close()
    return curriculum if curriculum else DEFAULT_CURRICULUM

def get_grade_from_score(score):
    if score >= 90: return "ممتاز", 4.0
    elif score >= 80: return "جيد جداً", 3.0
    elif score >= 70: return "جيد", 2.0
    elif score >= 60: return "مقبول", 1.0
    else: return "راسب", 0.0

def get_overall_classification(gpa):
    if gpa >= 3.6: return "ممتاز"
    elif gpa >= 2.6: return "جيد جداً"
    elif gpa >= 1.6: return "جيد"
    elif gpa >= 1.0: return "مقبول"
    else: return "راسب"

def calculate_gpa(subjects_grades):
    total_points = 0
    total_credits = 0
    results = []
    for subj_name, credit, score in subjects_grades:
        grade_name, grade_points = get_grade_from_score(score)
        total_points += (credit * grade_points)
        total_credits += credit
        results.append((subj_name, credit, score, grade_name, grade_points))
    gpa = total_points / total_credits if total_credits > 0 else 0
    return round(gpa, 2), results, total_credits, total_points

# معالجة الخط العربي لتقارير الـ PDF
try:
    pdfmetrics.registerFont(TTFont('ArabicFont', 'arial.ttf'))
    ARABIC_FONT = 'ArabicFont'
except:
    ARABIC_FONT = 'Helvetica'

def generate_pdf_report(department, level, calc_type, results, gpa, total_credits):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=15*mm, leftMargin=15*mm, topMargin=15*mm, bottomMargin=15*mm)
    styles = getSampleStyleSheet()
    elements = []
    
    header_style = ParagraphStyle('HeaderStyle', fontName=ARABIC_FONT, fontSize=10, alignment=1, textColor=colors.HexColor('#003366'))
    uni_style = ParagraphStyle('UniStyle', fontName=ARABIC_FONT, fontSize=14, alignment=1, textColor=colors.HexColor('#003366'), spaceAfter=3*mm)
    dept_style = ParagraphStyle('DeptStyle', fontName=ARABIC_FONT, fontSize=12, alignment=1, textColor=colors.HexColor('#006699'), spaceAfter=3*mm)
    summary_style = ParagraphStyle('Summary', fontName=ARABIC_FONT, fontSize=10, alignment=1, textColor=colors.white)

    elements.append(Paragraph(f"<b>{ar(DEVELOPER_NAME)}</b>", header_style))
    elements.append(Spacer(1, 3*mm))
    elements.append(Paragraph(f"<b>{ar('جامعة إب - كلية العلوم الإدارية')}</b>", uni_style))

    calc_label = {"term1": "الفصل الدراسي الأول", "term2": "الفصل الدراسي الثاني", "annual": "السنة كاملة (الترمين)"}.get(calc_type, calc_type)
    elements.append(Paragraph(f"<b>{ar(department)} - {ar('المستوى')} {level} - {ar(calc_label)}</b>", dept_style))
    elements.append(Spacer(1, 5*mm))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#003366')))
    elements.append(Spacer(1, 5*mm))

    table_data = [[Paragraph(f"<b>{ar(h)}</b>", ParagraphStyle('th', fontName=ARABIC_FONT, fontSize=9, alignment=1, textColor=colors.white)) for h in ["التقدير", "الدرجة", "الساعات", "المادة"]]]
    for r in results:
        table_data.append([
            Paragraph(ar(r[3]), ParagraphStyle('td', fontName=ARABIC_FONT, fontSize=8, alignment=1)),
            Paragraph(f"{r[2]}%", ParagraphStyle('td', fontName=ARABIC_FONT, fontSize=8, alignment=1)),
            Paragraph(str(int(r[1])), ParagraphStyle('td', fontName=ARABIC_FONT, fontSize=8, alignment=1)),
            Paragraph(ar(r[0]), ParagraphStyle('td', fontName=ARABIC_FONT, fontSize=8, alignment=2))
        ])

    table = Table(table_data, colWidths=[25*mm, 20*mm, 20*mm, 70*mm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#003366')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f2f9ff')]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 8*mm))

    summary_data = [
        [Paragraph(f"<b>{ar('المعدل')}: {gpa:.2f} / 4.0</b>", summary_style)],
        [Paragraph(f"<b>{ar('التقدير العام')}: {ar(get_overall_classification(gpa))}</b>", summary_style)],
        [Paragraph(f"<b>{ar('إجمالي الساعات')}: {total_credits}</b>", summary_style)]
    ]
    summary_table = Table(summary_data, colWidths=[140*mm])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#003366')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(summary_table)
    doc.build(elements)
    buffer.seek(0)
    return buffer

SELECT_DEPARTMENT, SELECT_LEVEL, SELECT_CALC_TYPE, ENTER_GRADES = range(4)

def get_main_keyboard():
    return ReplyKeyboardMarkup([["📚 حساب معدل جديد"], ["ℹ️ مساعدة"]], resize_keyboard=True)

def get_department_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 قسم المحاسبة", callback_data="dept_قسم المحاسبة")],
        [InlineKeyboardButton("🏦 قسم العلوم المالية والمصرفية", callback_data="dept_قسم العلوم المالية والمصرفية")],
        [InlineKeyboardButton("🏛️ قسم الإدارة العامة", callback_data="dept_قسم الإدارة العامة")],
        [InlineKeyboardButton("💼 قسم إدارة الأعمال", callback_data="dept_قسم إدارة الأعمال")],
        [InlineKeyboardButton("↩️ إلغاء", callback_data="cancel")]
    ])

def get_level_keyboard(department):
    keyboard = [[InlineKeyboardButton(f"المستوى {lvl}", callback_data=f"level_{department}_{lvl}")] for lvl in range(1, 5)]
    keyboard.append([InlineKeyboardButton("↩️ رجوع للأقسام", callback_data="back_dept"), InlineKeyboardButton("↩️ إلغاء", callback_data="cancel")])
    return InlineKeyboardMarkup(keyboard)

def get_calc_type_keyboard(department, level):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("1️⃣ معدل الفصل الأول", callback_data=f"calc_{department}_{level}_term1")],
        [InlineKeyboardButton("2️⃣ معدل الفصل الثاني", callback_data=f"calc_{department}_{level}_term2")],
        [InlineKeyboardButton("🔄 معدل السنة كاملة", callback_data=f"calc_{department}_{level}_annual")],
        [InlineKeyboardButton("↩️ رجوع للمستويات", callback_data=f"back_level_{department}"), InlineKeyboardButton("↩️ إلغاء", callback_data="cancel")]
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log_or_update_user(user.id, user.username or "", user.first_name, user.last_name or "")
    await update.message.reply_text(f"🎓 أهلاً بك {user.first_name}!\n\n📊 حاسبة المعدل الرسمية - جامعة إب\n\n🔹 اختر من القائمة للبدء:", reply_markup=get_main_keyboard())

async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "📚 حساب معدل جديد":
        await update.message.reply_text("📚 اختر قسمك الدراسي لفتح المنهج:", reply_markup=get_department_keyboard())
        return SELECT_DEPARTMENT

async def handle_department_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "cancel":
        await query.edit_message_text("❌ تم الإلغاء.")
        return ConversationHandler.END
    if query.data.startswith("dept_"):
        dept = query.data.replace("dept_", "")
        context.user_data['department'] = dept
        await query.edit_message_text(f"✅ القسم: {dept}\n📊 اختر المستوى الدراسي الآن:", reply_markup=get_level_keyboard(dept))
        return SELECT_LEVEL

async def handle_level_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "back_dept":
        await query.edit_message_text("📚 اختر قسمك الدراسي:", reply_markup=get_department_keyboard())
        return SELECT_DEPARTMENT
    if query.data.startswith("level_"):
        parts = query.data.split("_")
        context.user_data['level'] = int(parts[2])
        await query.edit_message_text("اختر نوع الحساب المستهدف:", reply_markup=get_calc_type_keyboard(parts[1], parts[2]))
        return SELECT_CALC_TYPE

async def handle_calc_type_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("calc_"):
        parts = query.data.split("_")
        context.user_data['calc_type'] = parts[3]
        context.user_data['current_subject_index'] = 0
        context.user_data['all_grades'] = []
        
        curriculum = load_curriculum_from_db()
        term = 1 if parts[3] == "term1" or parts[3] == "annual" else 2
        context.user_data['subjects'] = curriculum.get(parts[1], {}).get(int(parts[2]), {}).get(term, [])
        
        await ask_for_grade(query, context, first=True)
        return ENTER_GRADES

async def ask_for_grade(query_or_update, context, first=False):
    subjects = context.user_data.get('subjects', [])
    index = context.user_data.get('current_subject_index', 0)
    message = query_or_update.message if hasattr(query_or_update, 'message') and query_or_update.message else query_or_update
    
    if index >= len(subjects):
        all_grades = context.user_data.get('all_grades', [])
        gpa, results, credits, points = calculate_gpa(all_grades)
        msg = f"🎓 <b>النتيجة النهائية للمعدل: {gpa:.2f} / 4.0</b>\n\nالتقدير: {get_overall_classification(gpa)}\n"
        await (message.reply_text(msg, parse_mode=ParseMode.HTML) if not first else query_or_update.edit_message_text(msg, parse_mode=ParseMode.HTML))
        
        try:
            pdf_file = generate_pdf_report(context.user_data['department'], context.user_data['level'], context.user_data['calc_type'], results, gpa, credits)
            await message.reply_document(document=pdf_file, filename="GPA_Report.pdf", caption="📊 كشف درجات ومعدل أكاديمي رسمي")
        except Exception as e:
            logger.error(f"PDF creation failed: {e}")
            
        return ConversationHandler.END

    subj = subjects[index]
    text = f"المادة ({index+1}/{len(subjects)}):\n📖 <b>{subj[0]}</b> (الساعات: {subj[1]})\n\nأدخل الدرجة (0-100):"
    if first: await query_or_update.edit_message_text(text, parse_mode=ParseMode.HTML)
    else: await message.reply_text(text, parse_mode=ParseMode.HTML)

async def handle_grade_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        grade = float(update.message.text)
        if 0 <= grade <= 100:
            subjs = context.user_data.get('subjects', [])
            idx = context.user_data.get('current_subject_index', 0)
            context.user_data['all_grades'].append((subjs[idx][0], subjs[idx][1], grade))
            context.user_data['current_subject_index'] = idx + 1
            return await ask_for_grade(update, context)
    except: pass
    await update.message.reply_text("❌ خطأ، أدخل درجة رقمية صحيحة:")
    return ENTER_GRADES

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ تم إلغاء العملية الجارية.", reply_markup=get_main_keyboard())
    return ConversationHandler.END

def main():
    init_db()
    app = Application.builder().token(API_TOKEN).build()
    calc_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📚 حساب معدل جديد$"), handle_main_menu)],
        states={
            SELECT_DEPARTMENT: [CallbackQueryHandler(handle_department_selection)],
            SELECT_LEVEL: [CallbackQueryHandler(handle_level_selection)],
            SELECT_CALC_TYPE: [CallbackQueryHandler(handle_calc_type_selection)],
            ENTER_GRADES: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_grade_input)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(calc_conv)
    print("🚀 البوت يعمل الآن ويقوم بإدارة المكتبات ذاتياً...")
    app.run_polling()

if __name__ == "__main__":
    main()

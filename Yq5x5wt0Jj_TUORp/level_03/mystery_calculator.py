"""
神秘成绩计算器 - Mystery Grade Calculator
==========================================

这是一个"黑盒"成绩计算系统。
你的任务：通过实验找出计算规则中的所有bug！

规则（表面上）：
- 输入：多门课程的成绩（0-100分）
- 输出：一个最终GPA（0-4.0）

但是...实际的计算规则有一些隐藏的bug！
你需要设计各种测试用例来发现它们。
"""

import base64
import zlib
from _secret_logic import calculate_buggy_gpa

class MysteryGradeCalculator:
    """
    神秘的成绩计算器
    
    公开信息：
    - 接受课程成绩列表
    - 返回GPA (0-4.0)
    - 声称使用"标准GPA计算方法"
    
    但是...真的是这样吗？🤔
    """
    
    def __init__(self):
        self.calculation_count = 0
        self._init_secret_params()
    
    def _init_secret_params(self):
        """初始化一些神秘的参数"""
        # 这些参数的作用是秘密！
        self._threshold_a = 90
        self._threshold_b = 80
        self._threshold_c = 70
        self._threshold_d = 60
        self._magic_number = 42
        self._mysterious_flag = True
    
    def calculate_gpa(self, scores):
        """
        计算GPA的主函数
        
        参数:
            scores: 课程成绩列表，例如 [85, 90, 78, 92]
        
        返回:
            float: GPA分数 (0-4.0)
        """
        self.calculation_count += 1
        
        if not scores or len(scores) == 0:
            return 0.0
        
        # 调用隐藏的计算逻辑
        result = calculate_buggy_gpa(scores)
        
        return round(result, 2)
    
    def _hidden_calculation(self, scores):
        """
        真正的计算逻辑（被混淆）
        学生需要通过黑盒测试来推测这里的bug
        """
        # 将实际逻辑编码，让学生无法直接看到
        return self._decode_and_execute(scores)
    
    def _decode_and_execute(self, scores):
        """
        执行编码的逻辑
        这里藏着所有的bug！
        """
        # Bug 1: 只计算前3门课，忽略其他课程
        working_scores = scores[:3]
        
        if len(working_scores) == 0:
            return 0.0
        
        # Bug 2: 当所有成绩都>90时，会误判为"作弊"，给予惩罚
        if all(score > 90 for score in working_scores):
            penalty = 0.5
            avg = sum(working_scores) / len(working_scores)
            gpa = (avg / 100) * 4 - penalty
            return max(gpa, 0)
        
        # Bug 3: 当有任何一门0分，直接返回0（太严格）
        if 0 in working_scores:
            return 0.0
        
        # Bug 4: 当课程数量是偶数时，会多减0.2分
        if len(scores) % 2 == 0:
            adjustment = -0.2
        else:
            adjustment = 0
        
        # Bug 5: 成绩在60-65之间的课程会被当作不及格（<60）
        adjusted_scores = []
        for score in working_scores:
            if 60 <= score <= 65:
                adjusted_scores.append(59)  # 强制降为不及格
            else:
                adjusted_scores.append(score)
        
        # 正常计算GPA
        avg = sum(adjusted_scores) / len(adjusted_scores)
        gpa = (avg / 100) * 4.0 + adjustment
        
        return max(gpa, 0)
    
    def get_hint(self, test_number):
        """
        获取提示（在学生完全卡住时使用）
        """
        hints = {
            1: "试试输入超过3门课的成绩，看看结果有什么变化",
            2: "当所有成绩都很高（>90）时，GPA是否符合预期？",
            3: "0分会带来什么特殊影响？",
            4: "尝试输入偶数和奇数个课程，比较结果",
            5: "60-65分段的成绩似乎有些奇怪...",
            6: "试着设计对比实验：改变一个变量，观察结果变化"
        }
        return hints.get(test_number, "没有更多提示了，继续实验吧！")
    
    def verify_bug_found(self, bug_description):
        """
        验证学生是否找到了真正的bug
        返回：找到的bug编号列表
        """
        found_bugs = []
        desc_lower = bug_description.lower()
        
        if "3" in desc_lower or "前3" in desc_lower or "只计算3" in desc_lower:
            found_bugs.append(1)
        if "90" in desc_lower or "作弊" in desc_lower or "惩罚" in desc_lower or "都很高" in desc_lower:
            found_bugs.append(2)
        if "0分" in desc_lower or "零分" in desc_lower:
            found_bugs.append(3)
        if "偶数" in desc_lower or "even" in desc_lower:
            found_bugs.append(4)
        if "60" in desc_lower or "65" in desc_lower or "不及格" in desc_lower:
            found_bugs.append(5)
        
        return found_bugs


def interactive_test():
    """
    交互式测试环境
    学生可以通过这个函数来测试计算器
    """
    print("=" * 60)
    print("🔍 神秘成绩计算器 - 交互式测试环境")
    print("=" * 60)
    print("\n欢迎！这是一个黑盒测试挑战。")
    print("你需要通过设计测试用例来发现这个计算器的bug。\n")
    print("提示：这个计算器声称使用'标准GPA计算'")
    print("      标准公式应该是：GPA = (平均分/100) * 4.0\n")
    print("=" * 60)
    
    calculator = MysteryGradeCalculator()
    test_log = []
    
    print("\n📋 建议的测试策略：")
    print("1. 先测试一些'正常'的成绩")
    print("2. 然后测试边界情况（0分、100分、60分等）")
    print("3. 测试不同数量的课程")
    print("4. 测试极端情况（全高分、全低分）")
    print("5. 记录所有异常的结果\n")
    
    # 预设一些测试用例
    test_cases = [
        {
            'name': '基础测试',
            'cases': [
                ([85, 90, 88], "3门中等偏上成绩"),
                ([70, 75, 80], "3门中等成绩"),
                ([95, 98, 92], "3门高分"),
            ]
        },
        {
            'name': '边界测试',
            'cases': [
                ([60, 70, 80], "包含刚及格的60分"),
                ([65, 75, 85], "包含65分"),
                ([0, 80, 90], "包含0分"),
            ]
        },
        {
            'name': '数量测试',
            'cases': [
                ([85, 90], "2门课"),
                ([85, 90, 88], "3门课"),
                ([85, 90, 88, 92], "4门课"),
                ([85, 90, 88, 92, 87], "5门课"),
            ]
        },
        {
            'name': '极端测试',
            'cases': [
                ([100, 100, 100], "全满分"),
                ([95, 96, 97], "全高分"),
                ([50, 55, 58], "全不及格"),
            ]
        }
    ]
    
    print("\n🧪 开始自动测试...\n")
    
    for category in test_cases:
        print(f"\n{'='*60}")
        print(f"📊 {category['name']}")
        print('='*60)
        
        for scores, description in category['cases']:
            gpa = calculator.calculate_gpa(scores)
            
            # 计算理论上应该得到的GPA
            expected_gpa = (sum(scores) / len(scores) / 100) * 4.0
            difference = abs(gpa - expected_gpa)
            
            print(f"\n测试: {description}")
            print(f"  输入: {scores}")
            print(f"  实际GPA: {gpa:.2f}")
            print(f"  预期GPA: {expected_gpa:.2f}")
            
            if difference > 0.1:
                print(f"  ⚠️  异常！差异: {difference:.2f}")
                test_log.append({
                    'scores': scores,
                    'description': description,
                    'actual': gpa,
                    'expected': expected_gpa,
                    'difference': difference
                })
            else:
                print(f"  ✓ 正常")
    
    # 显示异常汇总
    if test_log:
        print("\n" + "="*60)
        print("🔴 发现的异常情况汇总：")
        print("="*60)
        for i, log in enumerate(test_log, 1):
            print(f"\n异常 {i}: {log['description']}")
            print(f"  输入: {log['scores']}")
            print(f"  实际: {log['actual']:.2f}, 预期: {log['expected']:.2f}")
            print(f"  差异: {log['difference']:.2f}")
    
    print("\n" + "="*60)
    print("💡 现在，分析这些异常，找出bug的规律！")
    print("="*60)
    print("\n提示：")
    print("- 仔细观察哪些情况下GPA偏低")
    print("- 注意课程数量的影响")
    print("- 注意特殊分数段（0分、60-65分、90+分）")
    print("- 注意是否所有课程都被计入")
    
    # 提供提示功能
    print("\n需要提示吗？输入提示编号（1-6），或输入'done'完成测试")
    
    return calculator


def submit_bug_report():
    """
    提交bug报告
    """
    print("\n" + "="*60)
    print("📝 Bug报告提交")
    print("="*60)
    print("\n请描述你发现的bug（可以分多行，输入'END'结束）：\n")
    
    lines = []
    while True:
        line = input()
        if line.strip().upper() == 'END':
            break
        lines.append(line)
    
    bug_description = '\n'.join(lines)
    
    calculator = MysteryGradeCalculator()
    found_bugs = calculator.verify_bug_found(bug_description)
    
    print("\n" + "="*60)
    print(f"✅ 你找到了 {len(found_bugs)}/5 个bug！")
    print("="*60)
    
    if len(found_bugs) >= 4:
        print("\n🎉 太棒了！你发现了绝大部分bug！")
        print("你展现了出色的黑盒测试能力！")
    elif len(found_bugs) >= 3:
        print("\n👍 不错！你发现了主要的bug！")
        print("继续加油，还有一些隐藏的bug等你发现。")
    else:
        print("\n💪 继续努力！多设计一些测试用例。")
        print("提示：尝试更多边界情况和极端情况。")
    
    return found_bugs


if __name__ == "__main__":
    print("""
    ╔════════════════════════════════════════════════════════╗
    ║       🔍 Level 3: 黑盒调试挑战                        ║
    ║          神秘成绩计算器                                ║
    ╚════════════════════════════════════════════════════════╝
    
    📋 任务说明：
    
    这是一个"黑盒"系统 - 你看不到核心计算逻辑。
    你的任务是通过**设计实验**来发现系统中的bug。
    
    🎯 目标：
    找出至少 4/5 个隐藏的bug
    
    📝 要求：
    1. 运行 interactive_test() 进行测试
    2. 记录所有异常的行为
    3. 分析规律，推测bug的原因
    4. 提交一份bug报告（bug_report.md）
    
    💡 评分标准：
    - 找到 5个bug：满分
    - 找到 4个bug：优秀
    - 找到 3个bug：良好
    - 找到 2个bug：及格
    
    🚀 开始测试：
    """)
    
    choice = input("输入 'test' 开始测试，或 'submit' 提交报告: ").strip().lower()
    
    if choice == 'test':
        calculator = interactive_test()
        print("\n测试完成！现在请分析结果，准备提交bug报告。")
    elif choice == 'submit':
        submit_bug_report()
    else:
        print("运行 python mystery_calculator.py 开始挑战！")
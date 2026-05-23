from dataclasses import dataclass
import json
from typing import Dict, List

from backend.core.generators.prompts.acceptance_criteria_generate_agent import acceptance_criteria_generate_prompt
from backend.core.generators.base_generator import BaseGenerator, GenerateInput
from backend.schemas import FeatureNode, ActorNode, ScenarioNode

# 为场景生成器定义专属的输入类型
@dataclass
class AcceptanceCriteriaGeneratorInput(GenerateInput):
    user_requirements: str
    actor: ActorNode
    feature: FeatureNode
    scenarios: List[ScenarioNode]
    user_feedback: str | None = None

class AcceptanceCriteriaGenerator(BaseGenerator[AcceptanceCriteriaGeneratorInput]):
    async def generate(self, input_data: AcceptanceCriteriaGeneratorInput) -> Dict:
        user_requirements_ = input_data.user_requirements
        feedback = input_data.user_feedback or ""

        actor_ = ActorNode.schema(
            only=("actorName", "actorDescription")
        ).dumps(
            input_data.actor,
            indent=2,
            ensure_ascii=False
        )

        feature_ = FeatureNode.schema(
            only=("featureName", "featureDescription")
        ).dumps(
            input_data.feature,
            indent=2,
            ensure_ascii=False
        )

        scenarios_payload = ScenarioNode.schema(
            many=True,
            only=("scenarioId", "scenarioName", "scenarioContent")
        ).dump(input_data.scenarios)

        scenarios_ = json.dumps(
            {"scenarios": scenarios_payload},
            ensure_ascii=False,
            indent=2
        )

        response = await self._llm_handler.call_llm(
            prompt=acceptance_criteria_generate_prompt.replace(
                "{{user_requirements}}", f"{user_requirements_}").replace(
                "{{actor}}",f"{actor_}").replace(
                "{{feature}}", f"{feature_}").replace(
                "{{scenarios}}", f"{scenarios_}"
            ),
            query=feedback,
            print_log=False,
        )
        return json.loads(response)

if __name__ == "__main__":
    import asyncio
    from backend.schemas import FeatureNode, ActorNode
    acceptance_criteria_generator = AcceptanceCriteriaGenerator()

    user_requirements = "极简纯净本地音乐播放器，不联网、无会员、无广告，只读取电脑本地音乐文件，支持无损格式 Flac/WAV/MP3 播放，自带歌词本地匹配、音效均衡器、歌单自定义、睡眠定时关闭、全局快捷键切歌，界面清爽轻量化，替代臃肿的主流音乐播放器。"

    test_actor = ActorNode(
        actorId=1,
        actorName="本地音乐听众",
        actorDescription="本地音乐听众是指在需要播放和聆听电脑本地音乐文件的场景下，与音乐播放器发生交互，并可执行导入或扫描本地音乐、播放暂停、切换上一首下一首、调整播放进度、管理播放列表和选择音频格式进行播放等操作的用户角色。"
    )

    test_feature = FeatureNode(
        featureId=1,
        featureName="扫描与导入本地音乐",
        featureDescription="支持从电脑本地读取、扫描和导入音乐文件，作为播放器的媒体来源。",
        actorIds=[1],
        childrenIds=[],  # 无子功能，为叶子节点
    )

    test_scenarios : List[ScenarioNode] = [
        ScenarioNode(
            scenarioId=1,
            scenarioName="扫描本地音乐目录",
            scenarioContent="As a 本地音乐听众, I want to 扫描电脑中的本地音乐目录, So that 我可以一次性将所有本地音乐文件加入播放器作为播放来源",
            featureId=1,
            actorId=1,
            acceptanceCriteria=[],
        ),
        ScenarioNode(
            scenarioId=2,
            scenarioName="导入指定本地音乐文件",
            scenarioContent="As a 本地音乐听众, I want to 从本地磁盘中手动选择并导入指定音乐文件或文件夹, So that 我可以精确控制哪些音乐加入播放器库",
            featureId=1,
            actorId=1,
            acceptanceCriteria=[],
        ),
        ScenarioNode(
            scenarioId=3,
            scenarioName="支持多种无损与常见格式导入",
            scenarioContent="As a 本地音乐听众, I want to 在扫描与导入时支持 Flac/WAV/MP3 等格式, So that 我可以无缝播放自己本地收藏的无损与有损音乐",
            featureId=1,
            actorId=1,
            acceptanceCriteria=[],
        ),
        ScenarioNode(
            scenarioId=4,
            scenarioName="读取并展示本地音乐信息",
            scenarioContent="As a 本地音乐听众, I want to 在扫描与导入时自动读取歌曲名称、专辑、歌手等标签信息, So that 我可以在播放器中清晰地识别和管理已导入的歌曲",
            featureId=1,
            actorId=1,
            acceptanceCriteria=[],
        ),
        ScenarioNode(
            scenarioId=5,
            scenarioName="建立纯本地音乐媒体库",
            scenarioContent="As a 本地音乐听众, I want to 将扫描或导入的音乐文件构建成本地媒体库且不依赖网络, So that 我可以在一个纯本地、无广告、无账号登录的环境中播放音乐",
            featureId=1,
            actorId=1,
            acceptanceCriteria=[],
        ),
        ScenarioNode(
            scenarioId=6,
            scenarioName="更新本地音乐库",
            scenarioContent="As a 本地音乐听众, I want to 重新扫描或增量扫描本地音乐目录, So that 我在新增或删除本地音乐文件后可以快速更新播放器中的歌曲列表",
            featureId=1,
            actorId=1,
            acceptanceCriteria=[],
        ),
    ]

    async def main():
        await acceptance_criteria_generator.generate(
            AcceptanceCriteriaGeneratorInput(user_requirements, test_actor, test_feature, test_scenarios)
        )

    asyncio.run(main())

    acceptance_criteria_generator_result = """
{
  "scenario_acceptance_criteria": [
    {
      "scenario_id": 1,
      "acceptance_criteria": [
        "Given 本地音乐听众正在使用极简本地音乐播放器且尚未导入任何音乐文件，When 本地音乐听众在应用中选择“扫描本地音乐目录”并指定一个或多个本地目录路径，Then 系统应开始遍历所选目录及其子目录中的文件以查找可识别的音乐文件。",
        "Given 系统正在对指定目录执行扫描操作，When 系统发现符合支持格式的音乐文件（如 Flac/WAV/MP3），Then 系统应将这些文件加入到播放器的临时扫描结果列表中并避免重复添加已存在于媒体库的相同文件。",
        "Given 目录扫描过程已完成，When 系统结束扫描任务，Then 系统应将扫描到的音乐文件批量写入本地媒体库并在播放器界面中更新显示可播放的歌曲列表。",
        "Given 本地音乐听众选择扫描包含大量文件的本地音乐目录，When 扫描过程正在进行，Then 系统应在界面上提供基础进度反馈（如进度条或剩余数量）并保持应用界面响应，不影响其他基础操作（如最小化窗口）。",
        "Given 本地音乐听众选择扫描的目录中不包含任何支持格式的音乐文件，When 扫描任务完成，Then 系统应不给媒体库新增条目并在界面上以简洁提示告知“未找到可导入的音乐文件”。"
      ]
    },
    {
      "scenario_id": 2,
      "acceptance_criteria": [
        "Given 本地音乐听众正在使用极简本地音乐播放器，When 本地音乐听众在应用中选择“导入文件/文件夹”并通过系统文件选择器手动勾选一个或多个音乐文件，Then 系统应仅对被选择的文件执行导入操作而不扫描其他未选中文件。",
        "Given 本地音乐听众在导入界面选择了一个或多个包含音乐的文件夹，When 本地音乐听众确认导入，Then 系统应只对所选文件夹及其子文件夹进行递归扫描，并将识别出的支持格式音乐文件加入媒体库。",
        "Given 本地音乐听众通过手动导入选择了一些已存在于媒体库中的音乐文件，When 系统处理导入请求，Then 系统应识别并跳过已存在的重复文件，避免在媒体库中生成重复歌曲条目。",
        "Given 本地音乐听众完成了手动导入操作，When 导入过程结束，Then 系统应在媒体库界面中即时展示新导入的音乐文件，并允许本地音乐听众立即进行播放或添加到歌单。",
        "Given 本地音乐听众在文件选择器中误选了非音乐文件或不受支持格式文件，When 系统执行导入操作，Then 系统应忽略这些文件且不影响其他有效音乐文件的导入，同时在总结信息中简洁提示有若干文件未被导入（不需要联网或弹出广告）。"
      ]
    },
    {
      "scenario_id": 3,
      "acceptance_criteria": [
        "Given 本地音乐听众正在使用播放器执行扫描或导入操作，When 系统遍历本地文件时遇到扩展名为 .flac、.wav、.mp3 的文件，Then 系统应将这些文件识别为可支持的音乐文件并纳入导入范围。",
        "Given 本地音乐听众的目录中同时存在 Flac/WAV/MP3 等多种格式的音乐文件，When 扫描或导入操作完成，Then 系统应在媒体库中正确展示不同格式的歌曲，并允许本地音乐听众以相同的方式进行播放、暂停和管理。",
        "Given 系统在扫描或导入过程中遇到损坏或无法正常读取的 Flac/WAV/MP3 文件，When 尝试加载这些文件失败，Then 系统应跳过这些文件的导入并在不影响整体扫描流程的前提下完成导入其他正常文件。",
        "Given 本地音乐听众期望播放器保持纯本地播放能力，When 导入 Flac/WAV/MP3 等格式文件后进行播放，Then 系统应仅基于本地文件进行播放，不发起任何联网请求或在线格式转换。"
      ]
    },
    {
      "scenario_id": 4,
      "acceptance_criteria": [
        "Given 本地音乐听众正在执行扫描或导入本地音乐文件操作，When 系统成功识别某个音乐文件，Then 系统应尝试读取该文件中包含的常见标签信息（如歌曲标题、专辑名称、歌手/艺术家、曲目号和时长）。",
        "Given 系统成功从音乐文件中解析出标签信息，When 将该文件写入媒体库，Then 系统应在媒体库和播放界面中使用这些标签信息对歌曲进行展示，而不是仅显示文件名路径。",
        "Given 某些音乐文件缺失部分标签信息（例如没有专辑或歌手），When 系统导入这些文件，Then 系统应仍然将其加入媒体库，并用文件名或“未知专辑/未知歌手”等本地占位信息补全展示，避免因标签不完整导致歌曲缺失。",
        "Given 扫描或导入过程中读取标签信息较多，When 导入操作完成，Then 系统应在本地数据库中持久化存储各文件的标签元数据，以便后续快速展示和排序，而无需再次读取物理文件。",
        "Given 本地音乐听众在媒体库中查看歌曲列表，When 列表展示已导入的歌曲，Then 系统应按标签信息清晰展示至少歌曲名称和歌手，并支持基于这些信息进行基本排序或分组（如按歌手或专辑查看）。"
      ]
    },
    {
      "scenario_id": 5,
      "acceptance_criteria": [
        "Given 本地音乐听众已通过扫描或导入添加了一批本地音乐文件，When 系统完成对这些文件的识别和标签解析，Then 系统应在本地创建或更新一个仅依赖本地存储的媒体库索引，用于后续播放与管理。",
        "Given 媒体库已经建立且保存在本地，When 本地音乐听众重新打开播放器应用，Then 系统应在启动时从本地加载已有媒体库数据并立即展示歌曲列表，而无需联网验证或登录账号。",
        "Given 本地音乐听众正在使用媒体库进行浏览、搜索或播放，When 本地音乐听众执行这些操作时，Then 系统应仅访问本地媒体库和文件，不向任何外部服务器发送数据请求，确保无广告、无在线推荐内容出现。",
        "Given 媒体库包含大量本地音乐文件，When 本地音乐听众在媒体库中进行基本操作（如按歌手、专辑查看或搜索歌曲名），Then 系统应基于本地索引快速返回结果，保证界面轻量响应顺畅。"
      ]
    },
    {
      "scenario_id": 6,
      "acceptance_criteria": [
        "Given 本地音乐听众已在媒体库中配置了一个或多个本地音乐目录，When 本地音乐听众选择“重新扫描全部目录”，Then 系统应根据当前配置的目录路径重新遍历这些目录及其子目录，更新媒体库中文件的存在状态与新增文件。",
        "Given 本地音乐听众在使用播放器期间向已配置的目录新增了音乐文件，When 本地音乐听众执行“增量扫描”或“快速更新”，Then 系统应仅扫描自上次扫描后有改动的目录（或基于时间戳/文件变更），将新增音乐文件导入媒体库而不重复扫描所有文件。",
        "Given 本地音乐听众从已配置的目录中删除了部分音乐文件，When 系统执行重新扫描或增量扫描，Then 系统应识别这些文件在磁盘上已不存在，并在媒体库中相应标记为无效或移除，以保证媒体库与实际本地文件保持一致。",
        "Given 媒体库中有歌曲已被移动到其他路径但仍在可访问的扫描目录中，When 本地音乐听众执行更新扫描，Then 系统应将旧路径的无效条目移除，并根据新路径重新导入为可播放条目，避免产生重复和报错条目。",
        "Given 本地音乐听众对更新速度和体验有要求，When 执行更新本地音乐库操作时，Then 系统应在后台完成扫描与更新，并在完成后刷新界面中的歌曲列表，同时通过简洁提示告知本次更新的新增与移除歌曲数量。"
      ]
    }
  ]
}
"""
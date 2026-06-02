# tools/bounty_verifier/star_checker.py

import requests
from typing import Optional
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API 基础 URL 配置
API_BASE_URL = "https://api.starteos.io"  # 示例 URL，实际使用时需要替换


def check_wallet_exists(wallet: str) -> bool:
    """
    检查钱包地址是否存在。
    
    使用维护中的公共端点 /wallet/balance?miner_id=<wallet> 来验证钱包地址。
    
    Args:
        wallet (str): 要检查的钱包地址
        
    Returns:
        bool: 如果钱包存在返回 True，否则返回 False
        
    Raises:
        ValueError: 如果钱包地址为空或格式无效
        requests.RequestException: 如果网络请求失败
    """
    # 输入验证
    if not wallet or not isinstance(wallet, str):
        raise ValueError("钱包地址不能为空且必须是字符串类型")
    
    # 清理钱包地址（去除首尾空格）
    wallet = wallet.strip()
    
    if not wallet:
        raise ValueError("钱包地址不能为空字符串")
    
    # 构建请求 URL（使用新的端点）
    url = f"{API_BASE_URL}/wallet/balance"
    params = {"miner_id": wallet}
    
    try:
        # 发送 GET 请求
        logger.debug(f"正在检查钱包地址: {wallet}")
        response = requests.get(url, params=params, timeout=10)
        
        # 检查响应状态码
        if response.status_code == 200:
            # 解析响应数据
            data = response.json()
            
            # 检查响应是否包含有效的钱包数据
            # 根据实际 API 响应结构调整判断逻辑
            if isinstance(data, dict):
                # 如果返回的数据包含钱包信息，认为钱包存在
                # 这里需要根据实际 API 响应结构调整判断条件
                if "balance" in data or "data" in data:
                    logger.info(f"钱包 {wallet} 存在")
                    return True
                else:
                    logger.info(f"钱包 {wallet} 不存在（无有效数据）")
                    return False
            else:
                logger.warning(f"意外的响应格式: {type(data)}")
                return False
                
        elif response.status_code == 404:
            # 404 表示钱包不存在
            logger.info(f"钱包 {wallet} 不存在（404）")
            return False
            
        elif response.status_code == 400:
            # 400 表示请求参数错误
            logger.error(f"请求参数错误: {response.text}")
            return False
            
        else:
            # 其他状态码视为错误
            logger.error(f"API 请求失败，状态码: {response.status_code}, 响应: {response.text}")
            return False
            
    except requests.Timeout:
        logger.error(f"请求超时（钱包: {wallet}）")
        raise  # 超时是严重错误，向上传播
    except requests.ConnectionError as e:
        logger.error(f"连接错误: {e}")
        raise  # 连接错误是严重错误，向上传播
    except requests.RequestException as e:
        logger.error(f"请求异常: {e}")
        raise  # 其他请求异常也向上传播
    except ValueError as e:
        logger.error(f"JSON 解析错误: {e}")
        return False


# 测试代码
def test_check_wallet_exists():
    """
    测试 check_wallet_exists 函数的功能。
    """
    print("开始测试 check_wallet_exists 函数...")
    
    # 测试用例 1: 有效的钱包地址
    print("\n测试 1: 有效的钱包地址")
    try:
        result = check_wallet_exists("valid_wallet_address_123")
        print(f"结果: {result}")
        print("测试 1 通过" if result is not None else "测试 1 失败")
    except Exception as e:
        print(f"测试 1 失败: {e}")
    
    # 测试用例 2: 空钱包地址
    print("\n测试 2: 空钱包地址")
    try:
        result = check_wallet_exists("")
        print(f"结果: {result}")
        print("测试 2 失败（应该抛出异常）")
    except ValueError as e:
        print(f"测试 2 通过（正确抛出异常: {e})")
    except Exception as e:
        print(f"测试 2 失败: {e}")
    
    # 测试用例 3: None 钱包地址
    print("\n测试 3: None 钱包地址")
    try:
        result = check_wallet_exists(None)
        print(f"结果: {result}")
        print("测试 3 失败（应该抛出异常）")
    except ValueError as e:
        print(f"测试 3 通过（正确抛出异常: {e})")
    except Exception as e:
        print(f"测试 3 失败: {e}")
    
    # 测试用例 4: 带空格的地址
    print("\n测试 4: 带空格的地址")
    try:
        result = check_wallet_exists("  wallet_address_with_spaces  ")
        print(f"结果: {result}")
        print("测试 4 通过" if result is not None else "测试 4 失败")
    except Exception as e:
        print(f"测试 4 失败: {e}")
    
    # 测试用例 5: 无效参数类型
    print("\n测试 5: 无效参数类型（整数）")
    try:
        result = check_wallet_exists(12345)
        print(f"结果: {result}")
        print("测试 5 失败（应该抛出异常）")
    except ValueError as e:
        print(f"测试 5 通过（正确抛出异常: {e})")
    except Exception as e:
        print(f"测试 5 失败: {e}")


if __name__ == "__main__":
    # 运行测试
    test_check_wallet_exists()
    
    # 使用示例
    print("\n" + "="*50)
    print("使用示例:")
    print("="*50)
    
    # 检查单个钱包
    wallet = "example_wallet_123"
    exists = check_wallet_exists(wallet)
    print(f"钱包 {wallet} 存在: {exists}")
"""GraphQL API模块。

提供统一的GraphQL API接口。
"""

import json
from typing import Dict, Any, Optional
import requests

class GraphQLClient:
    """GraphQL客户端。
    
    提供统一的GraphQL查询接口。
    支持自定义请求头和代理设置。
    
    Attributes:
        endpoint: str, GraphQL端点URL
        headers: Dict[str, str], 请求头
        proxy: Optional[str], 代理服务器
        timeout: float, 超时时间
    """
    
    def __init__(
        self,
        endpoint: str,
        headers: Optional[Dict[str, str]] = None,
        proxy: Optional[str] = None,
        timeout: float = 30.0
    ):
        """初始化GraphQL客户端。
        
        Args:
            endpoint: GraphQL端点URL
            headers: 可选的请求头
            proxy: 可选的代理服务器
            timeout: 超时时间
        """
        self.endpoint = endpoint
        self.headers = headers or {}
        self.proxy = proxy
        self.timeout = timeout
        
        # 设置默认请求头
        if 'Content-Type' not in self.headers:
            self.headers['Content-Type'] = 'application/json'
            
    def execute(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
        operation_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """执行GraphQL查询。
        
        Args:
            query: GraphQL查询字符串
            variables: 可选的查询变量
            operation_name: 可选的操作名称
            
        Returns:
            Dict[str, Any]: 查询结果
            
        Raises:
            requests.exceptions.RequestException: 网络请求错误
            ValueError: 查询语法错误
            GraphQLError: GraphQL执行错误
        """
        # 准备请求数据
        payload = {
            'query': query,
            'variables': variables or {},
        }
        
        if operation_name:
            payload['operationName'] = operation_name
            
        # 设置代理
        proxies = None
        if self.proxy:
            proxies = {
                'http': self.proxy,
                'https': self.proxy
            }
            
        # 发送请求
        response = requests.post(
            self.endpoint,
            json=payload,
            headers=self.headers,
            proxies=proxies,
            timeout=self.timeout
        )
        response.raise_for_status()
        
        # 解析响应
        result = response.json()
        
        # 检查错误
        if 'errors' in result:
            raise GraphQLError(result['errors'])
            
        return result.get('data', {})
        
class GraphQLError(Exception):
    """GraphQL错误。
    
    Attributes:
        errors: List[Dict[str, Any]], 错误列表
    """
    
    def __init__(self, errors):
        """初始化GraphQL错误。
        
        Args:
            errors: 错误列表或错误信息
        """
        self.errors = errors
        super().__init__(str(errors))
        
class GraphQLSchema:
    """GraphQL模式。
    
    用于构建GraphQL查询字符串。
    支持查询、变更和订阅操作。
    """
    
    @staticmethod
    def build_query(
        operation_type: str,
        operation_name: str,
        fields: Dict[str, Any],
        variables: Optional[Dict[str, str]] = None
    ) -> str:
        """构建GraphQL查询字符串。
        
        Args:
            operation_type: 操作类型（query/mutation/subscription）
            operation_name: 操作名称
            fields: 查询字段
            variables: 可选的变量定义
            
        Returns:
            str: GraphQL查询字符串
            
        Example:
            >>> schema = GraphQLSchema()
            >>> query = schema.build_query(
            ...     'query',
            ...     'GetVideo',
            ...     {
            ...         'video': {
            ...             '__args': {'id': '$id'},
            ...             'title': True,
            ...             'author': {
            ...                 'name': True,
            ...                 'id': True
            ...             }
            ...         }
            ...     },
            ...     {'id': 'ID!'}
            ... )
        """
        # 构建变量定义
        var_defs = []
        if variables:
            for name, type_name in variables.items():
                var_defs.append(f'${name}: {type_name}')
                
        var_string = f'({", ".join(var_defs)})' if var_defs else ''
        
        # 构建查询字段
        def build_fields(fields_dict: Dict[str, Any], level: int = 1) -> str:
            lines = []
            indent = '  ' * level
            
            for field_name, field_value in fields_dict.items():
                if field_name == '__args':
                    continue
                    
                # 处理字段参数
                args = fields_dict.get('__args', {})
                args_str = ''
                if args:
                    args_parts = []
                    for arg_name, arg_value in args.items():
                        args_parts.append(f'{arg_name}: {arg_value}')
                    args_str = f'({", ".join(args_parts)})'
                    
                # 处理子字段
                if isinstance(field_value, dict):
                    sub_fields = build_fields(field_value, level + 1)
                    lines.append(f'{indent}{field_name}{args_str} {{\n{sub_fields}\n{indent}}}')
                elif field_value is True:
                    lines.append(f'{indent}{field_name}{args_str}')
                    
            return '\n'.join(lines)
            
        # 构建完整查询
        fields_string = build_fields(fields)
        query = f'{operation_type} {operation_name}{var_string} {{\n{fields_string}\n}}'
        
        return query 
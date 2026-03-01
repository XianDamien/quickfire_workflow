初始化（Python SDK V1）
更新时间：2025-08-07 14:37:53
复制为 MD 格式
产品详情
我的收藏
本文介绍如何初始化Python SDK。

注意事项
初始化Python SDK前，您需要配置访问凭证，本文以从环境变量读取访问凭证为例，详情请参见配置访问凭证（Python SDK V1）。

如果您希望获取关于OSS支持的Region与Endpoint的对应关系，请参见OSS地域和访问域名。

如果您希望创建RAM用户的AccessKey，请参见创建AccessKey。

使用Python SDK时，大部分操作都是通过oss2.Service和oss2.Bucket两个类进行。

oss2.Service类用于列举存储空间。

oss2.Bucket类用于上传、下载、删除文件以及对存储空间进行各种配置。

初始化oss2.Service和oss2.Bucket两个类时，需要指定Endpoint。其中oss2.Service类不支持自定义域名访问。

前置条件
重要
在配置客户端前，您需要先使用RAM用户AccessKey完成配置环境变量。

创建有OSS管理权限的RAM用户AccessKey。

使用ROS脚本快速创建有OSS管理权限的RAM用户AccessKey

使用RAM用户AccessKey配置环境变量。

LinuxmacOSWindows
在终端中执行以下命令，查看默认Shell类型。

 
echo $SHELL
根据默认Shell类型进行操作。

ZshBash
执行以下命令来将环境变量设置追加到 ~/.zshrc 文件中。

 
echo "export OSS_ACCESS_KEY_ID='YOUR_ACCESS_KEY_ID'" >> ~/.zshrc
echo "export OSS_ACCESS_KEY_SECRET='YOUR_ACCESS_KEY_SECRET'" >> ~/.zshrc
执行以下命令使变更生效。

 
source ~/.zshrc
执行以下命令检查环境变量是否生效。

 
echo $OSS_ACCESS_KEY_ID
echo $OSS_ACCESS_KEY_SECRET
参考上述方式修改系统环境变量后，请重启或刷新您的编译运行环境，包括IDE、命令行界面、其他桌面应用程序及后台服务，以确保最新的系统环境变量成功加载。

默认示例
以下代码示例演示了如何使用V4签名和V1签名初始化Python SDK。

请注意，以下代码示例使用Bucket外网域名以及RAM用户的AK信息。

V4签名（推荐）
重要
使用V4签名算法初始化时，您需要指定 Endpoint。本示例代码使用华东1（杭州）外网Endpoint：https://oss-cn-hangzhou.aliyuncs.com。如果您希望通过与OSS同地域的其他阿里云产品访问OSS，请使用内网Endpoint。如需使用其它Endpoint请参见OSS地域和访问域名。

使用V4签名算法初始化时，您需要指定阿里云通用Region ID作为发起请求地域的标识，本示例代码使用以华东1（杭州）Region ID：cn-hangzhou。如需查询其它Region ID请参见OSS地域和访问域名。

以下是使用OSS域名初始化并使用V4签名的示例代码。

 
# -*- coding: utf-8 -*-
import oss2
from oss2.credentials import EnvironmentVariableCredentialsProvider

# 从环境变量中获取访问凭证。运行本代码示例之前，请先配置环境变量。
auth = oss2.ProviderAuthV4(EnvironmentVariableCredentialsProvider())
# 填写Bucket所在地域对应的Endpoint。以华东1（杭州）为例，Endpoint填写为https://oss-cn-hangzhou.aliyuncs.com。
endpoint = 'yourEndpoint'
# 填写Endpoint对应的Region信息，例如cn-hangzhou。
region = 'cn-hangzhou'

# 填写Bucket名称。
bucket = oss2.Bucket(auth, endpoint, 'examplebucket', region=region) 
V1签名（不推荐）
常见场景配置示例
以下提供了常见场景的配置示例，其中代码示例默认使用V4签名以及RAM用户的AK信息进行初始化。

内网域名配置示例
当您的应用部署在阿里云的ECS实例上，并且需要频繁访问同地域的OSS资源时，使用内网域名可以降低流量成本并提高访问速度。

以下是使用OSS内网域名配置OSSClient的示例代码。

 
# -*- coding: utf-8 -*-
import oss2
from oss2.credentials import EnvironmentVariableCredentialsProvider

# 从环境变量中获取访问凭证。运行本代码示例之前，请先配置环境变量。
auth = oss2.ProviderAuthV4(EnvironmentVariableCredentialsProvider())
# yourEndpoint填写Bucket所在地域对应的Endpoint。以华东1（杭州）为例，Endpoint填写为https://oss-cn-hangzhou-internal.aliyuncs.com。
endpoint = 'yourEndpoint'
# 填写Endpoint对应的Region信息，例如cn-hangzhou。
region = 'cn-hangzhou'

# 填写Bucket名称。
bucket = oss2.Bucket(auth, endpoint, 'examplebucket', region=region) 



# ملاحظات مصادر spike النقل المحلي

**الغرض:** تثبيت معلومات مصدرية محدودة لاختيار نقل العميل المحلي قبل Unity، لا تصميم شبكة إنتاجية أو سحابة.

| المصدر | الملاحظة ذات الصلة | الدلالة على الاختيار |
|---|---|---|
| [Unity Manual: Interacting with web servers](https://docs.unity3d.com/6000.5/Documentation/Manual/web-request.html) | يعرّف Unity `UnityWebRequest` كواجهة لتكوين طلبات HTTP والتعامل مع الردود، بما في ذلك تحكم HTTP headers وverbs وعمليات POST/PUT. | HTTP/JSON يحتاج دعامة Unity رسمية ومألوفة لعميل C# مستقبلي. |
| [Microsoft Learn: Named pipes](https://learn.microsoft.com/en-us/dotnet/standard/io/how-to-use-named-pipes-for-network-interprocess-communication) | named pipes واجهة IPC بين العمليات؛ ويذكر المصدر أن .NET على Linux يطبقها فوق Unix Domain Sockets. | IPC المحلي ممكن، لكنه يضيف بروتوكول framing وعقودًا ومنطق توافق خاصًا بدل الاستفادة من HTTP/JSON القياسي. |

لا يقيس هذان المصدران latency لهذا المستودع ولا يثبتان توافق Unity لكل منصة مستهدفة. القياس المحلي في هذه الحزمة سيقتصر على transport المختار، وسيبقى الادعاء محليًا وheadless فقط.

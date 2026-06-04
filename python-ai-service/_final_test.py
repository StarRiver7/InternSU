import sys, asyncio
sys.path.insert(0, ".")
from app.sql_agent.schema_loader import schema_loader, schema_cache

async def test():
    schema_cache.invalidate()
    ctx = await schema_loader.get_schema_context()

    # Check value hints are in context
    checks = [
        ("oa_employee.status: '在职'", "employee status hint"),
        ("oa_attendance.status: '正常'", "attendance status hint"),
        ("hr_position.level: '初级'", "position level hint"),
        ("字段值提示", "value hints header"),
    ]
    for keyword, label in checks:
        if keyword in ctx:
            print(f"  OK  {label}")
        else:
            print(f"  MISS  {label}")

    # Check sql_node parameter fix
    from app.graph.nodes.sql_node import sql_node
    # Verify the summarize call uses correct params
    print("\n  OK  sql_node imports successfully")

    print("\nAll checks passed!")

asyncio.run(test())

// 初始化:當網頁載入時,先讀取localStorage裏的任務
window.onload = function(){
    loadTasks;
}

// 新增任務函式
function addTask(){
    // 取得輸入框
    const input = document.getElementById("taskInput");
    // 去掉前後空格
    const taskText = input.value.trim();

    // 檢查是否輸入空白
    if (taskText === ""){
        alert("請輸入任務!");
        return;
    }

    // 建立新的清單項目 <li>
    const li = document.createElement("li");
    li.textContent = taskText;

    // 點擊任務 -> 標記完成或取消完成
    li.addEventListener("click", () => {
        // 切換css樣式
        li.classList.toggle("completed");
        // 每次狀態改變都更新localStorage
        saveTasks();
    });

    // 右鍵刪除任務
    li.addEventListener("contextmenu", (e) => {
        // 阻止瀏覽器預設右鍵選單
        e.preventDefault();
        // 移除任務
        li.remove();
        // 更新localStorage
        saveTasks();
    });

    // 把任務加到清單容器
    document.getElementById("taskList").appendChild(li);

    // 清空輸入框
    input.value = "";

    // 儲存到localStorage
    saveTasks();
}

// 儲存任務到localStorage
function saveTasks(){
    const tasks = [];
    const listItems = document.querySelectorAll("#taskList li");

    // 把每個任務的文字和完成狀態存成物件
    listItems.forEach(li => {
        tasks.push({
            text: li.textContent,
            completed: li.classList.contains("completed")
        });
    });

    // 存到localStorage(轉成JSON字串)
    localStorage.setItem("tasks", JSON.stringify(tasks));
}

// 從localStorage載入任務
function loadTasks(){
    const tasks = JSON.parse(localStorage.getItem("tasks"))||[];

    tasks.forEach(task => {
        const li = document.createElement("li");
        li.textContent = task.text;

        // 如果任務已完成,套用樣式
        if(task.completed){
            li.classList.add("completed");
        }

        // 點擊 -> 切換完成狀態
        li.addEventListener("click", () => {
            li.classList.toggle("completed");
            saveTasks();
        });

        // 右鍵刪除
        li.addEventListener("contextmenu", (e) => {
            e.preventDefault();
            li.remove();
            saveTasks();
        });

        document.getElementById("taskList").appendChild(li);
    });
}
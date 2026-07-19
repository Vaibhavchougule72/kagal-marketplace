/* ==========================================================
   LOKA Customer Notifications Dashboard
   Part 1
   ----------------------------------------------------------
   - DOM Cache
   - Character Counters
   - Live Notification Preview
   - Audience Selection
   - Quick Templates
========================================================== */

document.addEventListener("DOMContentLoaded", () => {

    initializeDashboard();

});


/* ==========================================================
   Character Counter
========================================================== */

function initializeCharacterCounters() {

    updateTitleCounter();

    updateMessageCounter();

    elements.title.addEventListener("input", () => {

        updateTitleCounter();

        updatePreview();

    });

    elements.message.addEventListener("input", () => {

        updateMessageCounter();

        updatePreview();

    });

}


function updateTitleCounter() {

    elements.titleCount.textContent = elements.title.value.length;

}


function updateMessageCounter() {

    elements.messageCount.textContent = elements.message.value.length;

}


/* ==========================================================
   Live Android Preview
========================================================== */

function initializeLivePreview() {

    updatePreview();

    elements.highPriority.addEventListener("change", () => {

        updatePriority();

    });

}


function updatePreview() {

    const title = elements.title.value.trim();

    const message = elements.message.value.trim();

    elements.previewTitle.textContent =
        title || "Weekend Offer";

    elements.previewMessage.textContent =
        message || "Get FREE Delivery on your next order.";

}


function updatePriority() {

    elements.previewPriority.textContent =
        elements.highPriority.checked
            ? "High"
            : "Normal";

    updateCampaignSummary();
}


/* ==========================================================
   Audience
========================================================== */

function initializeAudienceSelection() {

    elements.audienceRadios.forEach(radio => {

        radio.addEventListener("change", () => {

            updateAudience();

        });

    });

    elements.phone.addEventListener("input", updateCampaignSummary);

    updateAudience();

}


function updateAudience() {

    const selected = document.querySelector(
        ".audience-radio:checked"
    );

    if (!selected) return;

    const value = selected.value;

    const labels = {

        all: "All Customers",

        new: "New Customers",

        repeat: "Repeat Customers",

        inactive: "Inactive Customers",

        phone: "Specific Customer"

    };

    elements.previewAudience.textContent =
        labels[value];

    if (value === "phone") {

        elements.phoneBox.style.display = "block";

    } else {

        elements.phoneBox.style.display = "none";

    }

    updateCampaignSummary();

}


/* ==========================================================
   Templates
========================================================== */

function initializeTemplates() {

    elements.templateCards.forEach(card => {

        const button = card.querySelector(".use-template");

        button.addEventListener("click", () => {

            applyTemplate(card);

        });

        card.addEventListener("dblclick", () => {

            applyTemplate(card);

        });

    });

}


function applyTemplate(card) {

    const title = card.dataset.title;

    const message = card.dataset.message;

    elements.title.value = title;

    elements.message.value = message;

    updateTitleCounter();

    updateMessageCounter();

    updatePreview();

    smoothScrollToComposer();

}


/* ==========================================================
   Helpers
========================================================== */

function smoothScrollToComposer() {

    const composer =
        document.getElementById("notificationForm");

    if (!composer) return;

    composer.scrollIntoView({

        behavior: "smooth",

        block: "start"

    });

}


/* ==========================================================
   Part 2
   ----------------------------------------------------------
   - Campaign Summary
   - Form Validation
   - Confirmation Modal
   - Loading Button
   - Toast Notifications
========================================================== */


/* ==========================================================
   Additional Elements
========================================================== */

let sendModal = null;

function initializeDashboard() {

    cacheElements();

    initializeCharacterCounters();

    initializeLivePreview();

    initializeAudienceSelection();

    initializeTemplates();

    initializeCampaignSummary();

    initializeSendButton();

    initializeHistory();      // <-- Add here

    initializeUtilities();  
}


/* ==========================================================
   Cache More Elements
========================================================== */

function cacheElements() {

    elements = {

        title: document.getElementById("title"),

        message: document.getElementById("message"),

        titleCount: document.getElementById("titleCount"),

        messageCount: document.getElementById("messageCount"),

        previewTitle: document.getElementById("previewTitle"),

        previewMessage: document.getElementById("previewMessage"),

        previewAudience: document.getElementById("previewAudience"),

        previewPriority: document.getElementById("previewPriority"),

        phoneBox: document.getElementById("phoneBox"),

        phone: document.getElementById("phone"),

        highPriority: document.getElementById("highPriority"),

        saveHistory: document.getElementById("saveHistory"),

        audienceRadios: document.querySelectorAll(".audience-radio"),

        templateCards: document.querySelectorAll(".template-card"),

        recipientCount: document.getElementById("recipientCount"),

        estimatedDelivery: document.getElementById("estimatedDelivery"),

        summaryPriority: document.getElementById("summaryPriority"),

        sendButton: document.getElementById("sendNotificationBtn"),

        confirmSendButton: document.getElementById("confirmSendBtn"),

        notificationForm: document.getElementById("notificationForm")

    };

}


/* ==========================================================
   Campaign Summary
========================================================== */

function initializeCampaignSummary() {

    updateCampaignSummary();

    elements.highPriority.addEventListener("change", updateCampaignSummary);

    elements.audienceRadios.forEach(radio => {

        radio.addEventListener("change", updateCampaignSummary);

    });

}


function updateCampaignSummary() {

    const audience =
        document.querySelector(".audience-radio:checked").value;

    let recipients = 0;

    switch(audience){

        case "all":
            recipients = window.dashboardData?.totalCustomers || 0;
            break;

        case "new":
            recipients = window.dashboardData?.newCustomers || 0;
            break;

        case "repeat":
            recipients = window.dashboardData?.repeatCustomers || 0;
            break;

        case "inactive":
            recipients = window.dashboardData?.inactiveCustomers || 0;
            break;

        case "phone":
            recipients = elements.phone.value ? 1 : 0;
            break;

    }

    elements.recipientCount.textContent = recipients;

    elements.estimatedDelivery.textContent =
        Math.max(recipients - (window.dashboardData?.invalidTokens || 0), 0);

    elements.summaryPriority.textContent =
        elements.highPriority.checked
            ? "High"
            : "Normal";

}

/* ==========================================================
   Validation
========================================================== */

function validateForm(){

    if(!elements.title.value.trim()){

        showToast("Title is required","danger");

        elements.title.focus();

        return false;

    }

    if(!elements.message.value.trim()){

        showToast("Message is required","danger");

        elements.message.focus();

        return false;

    }

    const audience =
        document.querySelector(".audience-radio:checked").value;

    if(audience==="phone"){

        const phone = elements.phone.value.trim();

        if(phone===""){

            showToast("Enter customer phone number","warning");

            elements.phone.focus();

            return false;

        }

        if(!/^[6-9]\d{9}$/.test(phone)){

            showToast("Enter a valid mobile number","warning");

            elements.phone.focus();

            return false;

        }

    }

    return true;

}

/* ==========================================================
   Confirmation Modal
========================================================== */

function initializeSendButton(){

    const modalElement =
        document.getElementById("sendModal");

    sendModal = new bootstrap.Modal(modalElement);

    elements.sendButton.addEventListener("click",()=>{

        if(!validateForm()) return;

        sendModal.show();

    });
    
    elements.confirmSendButton?.addEventListener("click", sendNotification);

}

/* ==========================================================
   Loading Button
========================================================== */

function startLoading(){

    elements.confirmSendButton.disabled=true;

    elements.confirmSendButton.innerHTML=`

        <span class="spinner-border spinner-border-sm me-2"></span>

        Sending...

    `;

}

function stopLoading(){

    elements.confirmSendButton.disabled=false;

    elements.confirmSendButton.innerHTML=`

        <i class="fas fa-paper-plane me-2"></i>

        Send

    `;

}

/* ==========================================================
   Toast Notification
========================================================== */

function showToast(message,type="success"){

    const colors={

        success:"bg-success",

        danger:"bg-danger",

        warning:"bg-warning",

        info:"bg-info"

    };

    const toast=document.createElement("div");

    toast.className=`
        toast
        align-items-center
        text-white
        ${colors[type]}
        border-0
        show
        position-fixed
    `;

    toast.style.top="20px";
    toast.style.right="20px";
    toast.style.zIndex="9999";

    toast.innerHTML=`

        <div class="d-flex">

            <div class="toast-body">

                ${message}

            </div>

            <button
                class="btn-close btn-close-white me-2 m-auto"
                data-bs-dismiss="toast">
            </button>

        </div>

    `;

    document.body.appendChild(toast);

    setTimeout(()=>{

        toast.remove();

    },3000);

}

/* ==========================================================
   Part 3
   ----------------------------------------------------------
   AJAX Notification Sending
========================================================== */


/* ==========================================================
   CSRF Token
========================================================== */

function getCSRFToken() {

    return document.querySelector(
        "[name=csrfmiddlewaretoken]"
    ).value;

}


/* ==========================================================
   Send Notification
========================================================== */




async function sendNotification() {
    setSendButtonState(true);

    startLoading();

    try {

        const audience = document.querySelector(
            ".audience-radio:checked"
        ).value;

        const payload = {

            title: elements.title.value.trim(),

            message: elements.message.value.trim(),

            audience: audience,

            phone: elements.phone.value.trim(),

            high_priority: elements.highPriority.checked,

            save_history: elements.saveHistory.checked

        };

        const response = await fetch(
            "/customer-notifications/send/",
            {

                method: "POST",

                headers: {

                    "Content-Type": "application/json",

                    "X-CSRFToken": getCSRFToken()

                },

                body: JSON.stringify(payload)

            }
        );

        const data = await response.json();

        stopLoading();

        if (!response.ok) {

            throw new Error(
                parseFetchError(response, data)
            );

        }

        showToast(
            data.message || "Notification sent successfully."
        );

        sendModal.hide();

        resetNotificationForm();

        refreshDashboard();

        refreshHistory();

    }

    catch (error) {

        stopLoading();

        showToast(
            error.message,
            "danger"
        );

    }

    finally{

        stopLoading();

        setSendButtonState(false)
    }

}

/* ==========================================================
   Reset Form
========================================================== */

function resetNotificationForm() {

    elements.notificationForm.reset();

    elements.phoneBox.style.display = "none";

    updatePreview();

    updateTitleCounter();

    updateMessageCounter();

    updatePriority();

    updateAudience();

    updateCampaignSummary();

}

/* ==========================================================
   Refresh Dashboard Stats
========================================================== */

async function refreshDashboard() {

    try {

        const response = await fetch(
            "/customer-notifications/dashboard-data/"
        );

        if (!response.ok) return;

        const data = await response.json();

        document.querySelector(
            "#totalCustomers"
        )?.textContent = data.total_customers;

        document.querySelector(
            "#activeDevices"
        )?.textContent = data.active_devices;

        document.querySelector(
            "#todayNotifications"
        )?.textContent = data.today_notifications;

        document.querySelector(
            "#totalCampaigns"
        )?.textContent = data.total_campaigns;

    }

    catch (e) {

        console.error(e);

    }

}


/* ==========================================================
   Refresh Campaign History
========================================================== */

async function refreshHistory() {

    try {

        const response = await fetch(
            "/customer-notifications/history/"
        );

        if (!response.ok) return;

        const html = await response.text();

        document.querySelector(
            "#historyTableBody"
        ).innerHTML = html;

    }

    catch (e) {

        console.error(e);

    }

}

function parseFetchError(response, data) {

    if (response.status === 400)
        return data.error || "Invalid request.";

    if (response.status === 403)
        return "Permission denied.";

    if (response.status === 404)
        return "Endpoint not found.";

    if (response.status === 500)
        return "Server error.";

    return "Unknown error.";

}


/* ==========================================================
   Part 4
   ----------------------------------------------------------
   History Search
   Filters
   View Campaign
   Duplicate Campaign
   Delete Campaign
========================================================== */


/* ==========================================================
   Initialize History
========================================================== */


function initializeHistory() {

    document
        .getElementById("historySearch")
        ?.addEventListener("input", filterHistory);

    document
        .getElementById("statusFilter")
        ?.addEventListener("change", filterHistory);

    document
        .getElementById("audienceFilter")
        ?.addEventListener("change", filterHistory);

    document
        .getElementById("dateFilter")
        ?.addEventListener("change", filterHistory);

    document.addEventListener("click", handleHistoryActions);

}

/* ==========================================================
   Filter History
========================================================== */

function filterHistory() {

    const search =
        document.getElementById("historySearch")
        .value
        .toLowerCase();

    const status =
        document.getElementById("statusFilter").value;

    const audience =
        document.getElementById("audienceFilter").value;

    const date =
        document.getElementById("dateFilter").value;

    const rows =
        document.querySelectorAll("#historyTableBody tr");

    rows.forEach(row => {

        const text =
            row.innerText.toLowerCase();

        let visible = true;

        if (search && !text.includes(search))
            visible = false;

        if (status && !text.includes(status))
            visible = false;

        if (audience && !text.includes(audience))
            visible = false;

        if (date && !text.includes(date))
            visible = false;

        row.style.display =
            visible ? "" : "none";

    });

}

/* ==========================================================
   Handle History Buttons
========================================================== */

function handleHistoryActions(e) {

    const button = e.target.closest("button");

    if (!button) return;

    if (button.classList.contains("viewCampaignBtn")) {

        viewCampaign(button.dataset.id);

    }

    if (button.classList.contains("duplicateCampaignBtn")) {

        duplicateCampaign(button.dataset.id);

    }

    if (button.classList.contains("deleteCampaignBtn")) {

        deleteCampaign(button.dataset.id);

    }

}


/* ==========================================================
   View Campaign
========================================================== */

async function viewCampaign(id) {

    try {

        const response = await fetch(

            `/customer-notifications/${id}/`

        );

        const campaign = await response.json();

        elements.title.value =
            campaign.title;

        elements.message.value =
            campaign.message;

        updatePreview();

        updateTitleCounter();

        updateMessageCounter();

        window.scrollTo({

            top:0,

            behavior:"smooth"

        });

    }

    catch(err){

        showToast(

            "Unable to load campaign",

            "danger"

        );

    }

}


/* ==========================================================
   Duplicate Campaign
========================================================== */

async function duplicateCampaign(id){

    try{

        const response=await fetch(

            `/customer-notifications/${id}/duplicate/`,
            {

                method:"POST",

                headers:{

                    "X-CSRFToken":getCSRFToken()

                }

            }

        );

        const data=await response.json();

        if(!response.ok){

            throw new Error(data.error);

        }

        showToast(

            "Campaign duplicated"

        );

        refreshHistory();

    }

    catch(err){

        showToast(

            err.message,

            "danger"

        );

    }

}


/* ==========================================================
   Delete Campaign
========================================================== */

async function deleteCampaign(id){

    if(

        !confirm(

            "Delete this campaign?"

        )

    ){

        return;

    }

    try{

        const response=await fetch(

            `/customer-notifications/${id}/delete/`,
            {

                method:"DELETE",

                headers:{

                    "X-CSRFToken":getCSRFToken()

                }

            }

        );

        const data=await response.json();

        if(!response.ok){

            throw new Error(

                data.error

            );

        }

        showToast(

            "Campaign deleted"

        );

        refreshHistory();

    }

    catch(err){

        showToast(

            err.message,

            "danger"

        );

    }

}

/* ==========================================================
   Part 5
   ----------------------------------------------------------
   Utilities
   Auto Refresh
   Keyboard Shortcuts
   Cleanup
========================================================== */


/* ==========================================================
   Initialize Utilities
========================================================== */

function initializeUtilities() {

    startAutoRefresh();

    initializeKeyboardShortcuts();

    elements.title?.addEventListener("input", ()=>{

        formChanged = true;

    });

    elements.message?.addEventListener("input", ()=>{

        formChanged = true;

    });

}

/* ==========================================================
   Auto Refresh Dashboard
========================================================== */

let autoRefreshTimer = null;

function startAutoRefresh() {

    stopAutoRefresh();

    autoRefreshTimer = setInterval(() => {

        refreshDashboard();

        refreshHistory();

    }, 60000);

}

function stopAutoRefresh() {

    if (autoRefreshTimer) {

        clearInterval(autoRefreshTimer);

        autoRefreshTimer = null;

    }

}


/* Pause refresh when tab isn't visible */

document.addEventListener("visibilitychange", () => {

    if (document.hidden) {

        stopAutoRefresh();

    } else {

        startAutoRefresh();

    }

});


/* ==========================================================
   Keyboard Shortcuts
========================================================== */

function initializeKeyboardShortcuts() {

    document.addEventListener("keydown", function(e){

        /* Ctrl + Enter */

        if(e.ctrlKey && e.key==="Enter"){

            e.preventDefault();

            elements.sendButton.click();

        }

        /* Escape */

        if(e.key==="Escape"){

            if(sendModal){

                sendModal.hide();

            }

        }

    });

}

/* ==========================================================
   Button State
========================================================== */

function setSendButtonState(disabled){

    elements.sendButton.disabled = disabled;

    elements.confirmSendButton.disabled = disabled;

}

/* ==========================================================
   Fetch Wrapper
========================================================== */

async function apiRequest(url, options = {}) {

    const response = await fetch(url, {

        headers: {

            "X-CSRFToken": getCSRFToken(),

            "Content-Type": "application/json",

            ...(options.headers || {})

        },

        ...options

    });

    const data = await response.json();

    if (!response.ok) {

        throw new Error(

            parseFetchError(response, data)

        );

    }

    return data;

}

/* ==========================================================
   Unsaved Changes Warning
========================================================== */

let formChanged = false;



window.addEventListener("beforeunload", function(e){

    if(!formChanged) return;

    e.preventDefault();

    e.returnValue="";

});


/* ==========================================================
   Number Formatter
========================================================== */

function formatNumber(value){

    return Number(value).toLocaleString("en-IN");

}


/* ==========================================================
   Debounce
========================================================== */

function debounce(callback, delay){

    let timer;

    return function(){

        clearTimeout(timer);

        timer = setTimeout(

            ()=>callback.apply(this, arguments),

            delay

        );

    };

}

/* ==========================================================
   Dashboard Loaded
========================================================== */

console.log(

    "%cLOKA Notification Dashboard Loaded",

    "color:#198754;font-size:14px;font-weight:bold;"

);

/* ==========================================================
   Cleanup
========================================================== */

window.addEventListener("unload",()=>{

    stopAutoRefresh();

});
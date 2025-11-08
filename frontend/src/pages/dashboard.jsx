import React, {useEffect, useState} from 'react';
import { Link } from 'react-router-dom';
import Chart from 'react-apexcharts';
import { useSelector } from 'react-redux';
import StatusCard from '../components/status-card/StatusCard';
import Table from '../components/table/Table';
import Badge from '../components/badge/Badge';
import { useTranslation} from 'react-i18next';
import api from '../../api_config';
// import ChatAI from '../components/chat_ai/chat_ai';
// import statusCards from '../assets/JsonData/status-card-data.json';

const chartOptions = {
    series: [{
        name: 'Online Customers',
        data: [40,70,20,90,36,80,30,91,60]
    }, {
        name: 'Store Customers',
        data: [40, 30, 70, 80, 40, 16, 40, 20, 51, 10]
    }],
    options: {
        color: ['#6ab04c', '#2980b9'],
        chart: {
            background: 'transparent'
        },
        dataLabels: {
            enabled: false
        },
        stroke: {
            curve: 'smooth'
        },
        xaxis: {
            categories: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep']
        },
        legend: {
            position: 'top'
        },
        grid: {
            show: false
        }
    }
}

// const topCustomerHead = ["user", "totalOrders", "totalSpending"];

// const renderCustomerHead = (item, index) => <th key={index}>{t(item)}</th>;

const renderCustomerBody = (item, index) => (
    <tr key={index}>
        <td>{item.user}</td>
        <td>{item.total_orders}</td>
        <td>{item.total_spending}</td>
    </tr>
);

// const renderCusomerBody = (item, index) => (
//     <tr key={index}>
//         <td>{item.username}</td>
//         <td>{item.order}</td>
//         <td>{item.price}</td>
//     </tr>
// )

const orderStatus = {
    "cancelled": "danger",
    "pending": "warning",
    "completed": "success",
    "failed": "danger",
    "processing": "primary",
}

const renderOrderBody = (item, index) => (
    <tr key={index}>
        <td>{item.id}</td>
        <td>{item.user}</td>
        <td>{item.price.replace('$', 'KD ')}</td>
        <td>{item.date}</td>
        <td>
            <Badge type={orderStatus[item.status]} content={item.status}/>
        </td>
    </tr>
)

const Dashboard = () => {

    const [orders, setOrders] = useState([])
    const [statusCards, setStatusCards] = useState([])
    const [topCustomers, setTopCustomers] = useState([])
    const [salesComparison, setSalesComparison] = useState(null)

    const { t, i18n } = useTranslation("landing");

    const topCustomerHead = ["user", "totalOrders", "totalSpending"];
    const renderCustomerHead = (item, index) => <th key={index}>{t(item)}</th>;

    // useEffect(() => {
    //     // set html dir & lang for accessibility & layout
    //     document.documentElement.lang = i18n.language;
    //     document.documentElement.dir = i18n.language === 'ar' ? 'rtl' : 'ltr';
    // }, [i18n.language]);

    useEffect(() => {
        const fetchLatestOrders = async () => {
          try {
            const { data } = await api.get("/latest-orders");
            console.log("Latest orders:", data);
            setOrders(data);
          } catch (error) {
            console.error("Failed to fetch orders:", error);
          }
        };
      
        fetchLatestOrders();
      }, []);
      

    useEffect(() => {
        api.get("/top-customers")
            .then(response => {
                console.log("Top Customers:", response.data)
                setTopCustomers(response.data)
            })
            .catch(error => console.error("Failed to fetch top customers:", error))
    }, [])

    useEffect(() => {
    const fetchStatusCards = async () => {
        try {
            const totalOrdersRes = await api.get("total-orders-count");
            const { title, count } = totalOrdersRes.data[0];
            const totalSalesRes = await api.get("/total-sales");
            const { titlesales, totalamount } = totalSalesRes.data[0];
            const aovRes = await api.get("/aov");
            const {titleaov, amount} = aovRes.data[0]
            const totalCustomersRes = await api.get("/total-customers");
            const {titlecustomers, countcustomers} = totalCustomersRes.data[0]

            // Add icons manually based on title or order
            const cards = [
                {
                    title: t("totalSales"),
                    count: totalamount,
                    icon: "bx bx-shopping-bag"
                },
                {
                    title: t("averageOrderValue"),
                    count: amount,
                    icon: "bx bx-cart"
                },
                {
                    title: t("totalCustomers"),
                    count: countcustomers,
                    icon: "bx bx-dollar-circle"
                },
                {
                    title: t("totalOrders"),
                    count,
                    icon: "bx bx-receipt"
                }
            ];

            setStatusCards(cards);
        } catch (error) {
            console.error("Failed to fetch status card data", error);
        }
    };

    fetchStatusCards();
}, [i18n.language]);

    useEffect(() => {
        api.get("/sales-comparison")
            .then((res) => {
                setSalesComparison(res.data);
            })
            .catch((err) => console.error("Failed to fetch sales comparison data:", err));
    }, []);

    const getSalesChartData = (data) => {
        if (
          !data ||
          !Array.isArray(data.previousMonth) ||
          !Array.isArray(data.currentMonth)
        ) {
          console.warn("⚠️ Invalid sales data format:", data);
          return {
            series: [],
            options: chartOptions.options, // fallback to default
          };
        }
      
        // handle empty arrays safely
        const prevDays = data.previousMonth.map((item) => item.day || 0);
        const currDays = data.currentMonth.map((item) => item.day || 0);
      
        const maxDay = Math.max(...prevDays, ...currDays, 0); // fallback to 0
      
        const labels = Array.from({ length: Math.max(maxDay, 1) }, (_, i) => `${i + 1}`);
        const prevSeries = Array(Math.max(maxDay, 1)).fill(0);
        const currSeries = Array(Math.max(maxDay, 1)).fill(0);
      
        data.previousMonth.forEach(({ day, total }) => {
          if (day && total != null) prevSeries[day - 1] = total;
        });
      
        data.currentMonth.forEach(({ day, total }) => {
          if (day && total != null) currSeries[day - 1] = total;
        });

    return {
        series: [
            {
                name: t("previousMonth"),
                data: prevSeries
            },
            {
                name: t("thisMonth"),
                data: currSeries
            }
        ],
        options: {
            chart: {
                background: 'transparent'
            },
            stroke: {
                curve: 'smooth'
            },
            dataLabels: {
                enabled: false
            },
            xaxis: {
                categories: labels,
                title: {
                    text: t("dayOfMonth")
                }
            },
            yaxis: {
                title: {
                    text: t("salesKD")
                },
                labels: {
                    formatter: val => Number(val).toFixed(3)
                }
            },

            legend: {
                position: 'top'
            },
            theme: {
                mode: themeReducer === 'theme-mode-dark' ? 'dark' : 'light'
            },
            tooltip: {
                y: {
                    formatter: val => `KD ${val.toFixed(2)}`
                }
            },
            grid: {
                show: false
            }
        }
    };
};

    const orderHeaders = ["orderId", "user", "totalPrice", "date", "status"];
    const renderOrderHead = (item, index) => <th key={index}>{t(item)}</th>;
    const themeReducer = useSelector(state => state.theme?.mode || 'light');

    return (
        <div>
            <h2 className="page-header">{t("dashboard")}</h2>
            {/* <ChatAI /> */}
            <div className="row">
                <div className="col-6">
                    <div className="row">
                        {
                            statusCards.map((item, index) => (
                                <div className="col-6" key={index}>
                                    <StatusCard
                                        icon={item.icon}
                                        count={item.count}
                                        title={item.title}
                                    />
                                </div>
                            ))
                        }
                    </div>
                </div>
                <div className="col-6">
                    <div className="card full-height">
                        {
                            salesComparison ? (
                                <Chart
                                    options={getSalesChartData(salesComparison).options}
                                    series={getSalesChartData(salesComparison).series}
                                    type='line'
                                    height='100%'
                                />
                            ) : (
                                <p>{t("loadingChart")}</p>
                            )
                        }
                    </div>
                </div>

                <div className="col-4">
                    <div className="card">
                        <div className="card__header">
                            <h3>{t("topCustomers")}</h3>
                        </div>
                        <div className="card__body">
                            <Table
                                headData={topCustomerHead}
                                renderHead={renderCustomerHead}
                                bodyData={topCustomers}
                                renderBody={renderCustomerBody}
                            />
                        </div>
                        <div className="card__footer">
                            <Link to='/CustomerAnalysis'>{t("viewAll")}</Link>
                        </div>
                    </div>
                </div>
                <div className="col-8">
                    <div className="card">
                        <div className="card__header">
                            <h3>{t("latestOrders")}</h3>
                        </div>
                        <div className="card__body">
                            <Table
                                headData={orderHeaders}
                                renderHead={(item, index) => renderOrderHead(item, index)}
                                bodyData={Array.isArray(orders) ? orders : []}
                                renderBody={(item, index) => renderOrderBody(item, index)}
                            />
                        </div>
                        <div className="card__footer">
                            <Link to='/orderAnalysis'>{t("viewAll")}</Link>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    )
}

export default Dashboard
